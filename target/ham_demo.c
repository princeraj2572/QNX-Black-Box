/*
 * HAM recovery demo: the High Availability Manager restarts a killed service.
 *
 *   ./ham_demo register /tmp/ham_demo   ask a running ham to start and watch
 *                                       "/tmp/ham_demo worker", restarting it
 *                                       whenever it dies, then exit
 *   ./ham_demo worker                   the service: a 10 ms periodic job
 *
 * The worker thread is named "worker" and logs "blackbox RELEASED"/"DONE" per
 * job, so after a kill the trace shows one "worker" instance stop and a new
 * one (new pid, so a new tid in the internal format) start. `blackbox
 * recovery` measures that gap.
 *
 * API from the SDP 8.0 HAM reference (ha/ham.h, libham): ham_connect,
 * ham_attach, ham_condition(CONDDEATH), ham_action_restart, ham_disconnect.
 * TODO(human): not yet built or run on a target. Check that the entity
 * outlives ham_disconnect() and that both HREARMAFTERRESTART flags keep
 * restarts going after the first one.
 */

#include <ha/ham.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <string.h>
#include <sys/trace.h>
#include <time.h>

#define PERIOD_MS 10
#define TRACE_CODE 100 /* any user event code; the adapter matches the text */

static int worker(void)
{
    struct sched_param sp;
    struct timespec next;
    memset(&sp, 0, sizeof sp);
    sp.sched_priority = 15;
    if (pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp) != 0)
        fprintf(stderr, "worker: cannot set priority 15 (run as root?)\n");
    pthread_setname_np(pthread_self(), "worker");
    clock_gettime(CLOCK_MONOTONIC, &next);
    for (;;) {
        next.tv_nsec += PERIOD_MS * 1000000L;
        while (next.tv_nsec >= 1000000000L) {
            next.tv_nsec -= 1000000000L;
            next.tv_sec++;
        }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        trace_logf(TRACE_CODE, "blackbox RELEASED");
        trace_logf(TRACE_CODE, "blackbox DONE");
    }
}

static int register_worker(const char *path)
{
    char line[512];
    ham_entity_t *e;
    ham_condition_t *c;
    snprintf(line, sizeof line, "%s worker", path);
    if (ham_connect(0) == -1) {
        perror("ham_connect (is ham running?)");
        return 1;
    }
    /* pid -1: ham starts the process itself from line, and watches it. */
    e = ham_attach("worker", 0, -1, line, 0);
    c = e ? ham_condition(e, CONDDEATH, "died", HREARMAFTERRESTART) : NULL;
    if (!c || !ham_action_restart(c, "restart", line, HREARMAFTERRESTART)) {
        perror("ham setup");
        ham_disconnect(0);
        return 1;
    }
    ham_disconnect(0);
    printf("ham now runs and restarts: %s\n", line);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "worker") == 0)
        return worker();
    if (argc >= 3 && strcmp(argv[1], "register") == 0)
        return register_worker(argv[2]);
    fprintf(stderr, "usage: %s register /full/path/to/ham_demo | worker\n", argv[0]);
    return 2;
}
