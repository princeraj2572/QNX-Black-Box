/*
 * Priority-inversion demo for QNX Black Box.
 *
 *   inversion_demo [seconds] [--fixed]
 *
 * Threads (all SCHED_FIFO, one process, one channel):
 *   controller  prio 20  every 50 ms sends a message to the server; wants the
 *                        reply within 20 ms
 *   server      prio 5   receives the message, takes the shared mutex, replies
 *   low         prio 5   holds the shared mutex 10 ms on, 10 ms off; after
 *                        2 s, every 10th time it wakes med while holding it
 *   med         prio 10  busy-loops for 60 ms each time it is woken
 *
 * All threads share one CPU. Without --fixed the mutex has no priority
 * inheritance: med preempts low while low holds the mutex, the server (and
 * so the controller) waits ~60 ms, and the 20 ms deadline is missed. With
 * --fixed (PTHREAD_PRIO_INHERIT) low runs at the waiting server's priority,
 * med cannot preempt it, and the deadline holds.
 *
 * Checked on QNX 8.0 (x86_64 QEMU): the server runs at the controller's
 * priority (20) after MsgReceive, yet still waits on the mutex.
 * Thread names (pthread_setname_np) show up in the trace. The controller logs
 * "blackbox RELEASED"/"blackbox DONE" user events, which the tracelogger
 * adapter turns into job markers.
 */
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <semaphore.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/neutrino.h>
#include <sys/trace.h>
#include <time.h>
#include <unistd.h>

#define PERIOD_MS 50
#define DEADLINE_MS 20
#define HOLD_MS 10 /* short enough for the deadline unless med preempts the holder */
#define TRACE_CODE 100 /* any user event code; the adapter matches the text */

static pthread_mutex_t shared;
static int chid;
static volatile int running = 1;
static sem_t med_go; /* low wakes med while holding the mutex */

static void set_self(const char *name, int prio)
{
    struct sched_param sp;
    memset(&sp, 0, sizeof sp);
    sp.sched_priority = prio;
    if (pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp) != 0)
        fprintf(stderr, "%s: cannot set priority %d (run as root?)\n", name, prio);
    pthread_setname_np(pthread_self(), name);
    /* One CPU for every thread: on SMP, med would run beside low instead of
     * preempting it, and there would be no inversion to show. */
    if (ThreadCtl(_NTO_TCTL_RUNMASK, (void *)1) == -1)
        perror("ThreadCtl runmask");
}

static long elapsed_ms(const struct timespec *a, const struct timespec *b)
{
    return (b->tv_sec - a->tv_sec) * 1000L + (b->tv_nsec - a->tv_nsec) / 1000000L;
}

static void burn_ms(long ms)
{
    struct timespec start, now;
    clock_gettime(CLOCK_MONOTONIC, &start);
    do {
        clock_gettime(CLOCK_MONOTONIC, &now);
    } while (elapsed_ms(&start, &now) < ms);
}

static void *low_thread(void *arg)
{
    (void)arg;
    int n = 0;
    set_self("low", 5);
    while (running) {
        pthread_mutex_lock(&shared);
        /* After a quiet 2 s, every 10th critical section gets interrupted. */
        if (++n > 2000 / (2 * HOLD_MS) && n % 10 == 0)
            sem_post(&med_go);
        burn_ms(HOLD_MS);
        pthread_mutex_unlock(&shared);
        usleep(HOLD_MS * 1000);
    }
    return NULL;
}

static void *med_thread(void *arg)
{
    (void)arg;
    set_self("med", 10);
    while (running) {
        sem_wait(&med_go);
        burn_ms(60);
    }
    return NULL;
}

static void *server_thread(void *arg)
{
    int msg, reply = 0;
    (void)arg;
    set_self("server", 5);
    while (running) {
        int rcvid = MsgReceive(chid, &msg, sizeof msg, NULL);
        if (rcvid <= 0)
            continue;
        pthread_mutex_lock(&shared);
        pthread_mutex_unlock(&shared);
        MsgReply(rcvid, EOK, &reply, sizeof reply);
    }
    return NULL;
}

static void *controller_thread(void *arg)
{
    int coid = ConnectAttach(0, 0, chid, _NTO_SIDE_CHANNEL, 0);
    struct timespec next, sent, done;
    int msg = 1, reply;
    (void)arg;
    set_self("controller", 20);
    if (coid == -1) {
        perror("ConnectAttach");
        return NULL;
    }
    clock_gettime(CLOCK_MONOTONIC, &next);
    while (running) {
        next.tv_nsec += PERIOD_MS * 1000000L;
        while (next.tv_nsec >= 1000000000L) {
            next.tv_nsec -= 1000000000L;
            next.tv_sec++;
        }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        trace_logf(TRACE_CODE, "blackbox RELEASED");
        clock_gettime(CLOCK_MONOTONIC, &sent);
        if (MsgSend(coid, &msg, sizeof msg, &reply, sizeof reply) == -1)
            perror("MsgSend");
        clock_gettime(CLOCK_MONOTONIC, &done);
        trace_logf(TRACE_CODE, "blackbox DONE");
        if (elapsed_ms(&sent, &done) > DEADLINE_MS)
            printf("controller: reply took %ld ms (deadline %d ms)\n",
                   elapsed_ms(&sent, &done), DEADLINE_MS);
    }
    return NULL;
}

int main(int argc, char **argv)
{
    int seconds = argc > 1 ? atoi(argv[1]) : 10;
    /* --fixed: priority inheritance on the mutex, so low runs at the waiting
     * server's priority and med can no longer preempt it. */
    int fixed = argc > 2 && strcmp(argv[2], "--fixed") == 0;
    pthread_mutexattr_t attr;
    pthread_t t[4];

    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setprotocol(&attr, fixed ? PTHREAD_PRIO_INHERIT : PTHREAD_PRIO_NONE);
    pthread_mutex_init(&shared, &attr);

    sem_init(&med_go, 0, 0);
    chid = ChannelCreate(0);
    if (chid == -1) {
        perror("ChannelCreate");
        return 1;
    }
    pthread_create(&t[0], NULL, server_thread, NULL);
    pthread_create(&t[1], NULL, low_thread, NULL);
    pthread_create(&t[2], NULL, med_thread, NULL);
    pthread_create(&t[3], NULL, controller_thread, NULL);

    sleep(seconds);
    running = 0;
    /* server_thread may stay blocked in MsgReceive; exit without joining it. */
    pthread_join(t[3], NULL);
    return 0;
}
