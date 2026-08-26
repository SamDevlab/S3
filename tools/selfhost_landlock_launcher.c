#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef LANDLOCK_CREATE_RULESET_VERSION
#define LANDLOCK_CREATE_RULESET_VERSION 1U
#endif

#ifndef LANDLOCK_RULE_PATH_BENEATH
#define LANDLOCK_RULE_PATH_BENEATH 1
#endif

#ifndef LANDLOCK_ACCESS_FS_EXECUTE
#define LANDLOCK_ACCESS_FS_EXECUTE (1ULL << 0)
#endif

#ifndef LANDLOCK_ACCESS_FS_READ_FILE
#define LANDLOCK_ACCESS_FS_READ_FILE (1ULL << 2)
#endif

enum {
    EXIT_USAGE = 124,
    EXIT_UNSUPPORTED = 125,
    EXIT_SANDBOX_FAILURE = 126
};

static int fail(const char *label, int status) {
    int saved = errno;
    if (saved != 0) {
        dprintf(STDERR_FILENO, "S3_LANDLOCK_%s errno=%d\n", label, saved);
    } else {
        dprintf(STDERR_FILENO, "S3_LANDLOCK_%s\n", label);
    }
    return status;
}

int main(int argc, char **argv, char **envp) {
    if (argc < 2) {
        errno = 0;
        return fail("USAGE", EXIT_USAGE);
    }

#if !defined(__NR_landlock_create_ruleset) || \
    !defined(__NR_landlock_add_rule) || \
    !defined(__NR_landlock_restrict_self)
    errno = 0;
    return fail("UNSUPPORTED_HEADERS", EXIT_UNSUPPORTED);
#else
    int abi = (int)syscall(
        __NR_landlock_create_ruleset,
        NULL,
        0,
        LANDLOCK_CREATE_RULESET_VERSION
    );
    if (abi < 1) {
        return fail("UNSUPPORTED_KERNEL", EXIT_UNSUPPORTED);
    }

    const uint64_t handled =
        LANDLOCK_ACCESS_FS_EXECUTE |
        LANDLOCK_ACCESS_FS_READ_FILE;
    struct landlock_ruleset_attr ruleset = {
        .handled_access_fs = handled,
    };
    int ruleset_fd = (int)syscall(
        __NR_landlock_create_ruleset,
        &ruleset,
        sizeof(ruleset),
        0
    );
    if (ruleset_fd < 0) {
        return fail("CREATE_RULESET", EXIT_SANDBOX_FAILURE);
    }

    int compiler_fd = open(argv[1], O_PATH | O_CLOEXEC);
    if (compiler_fd < 0) {
        close(ruleset_fd);
        return fail("OPEN_COMPILER", EXIT_SANDBOX_FAILURE);
    }

    struct landlock_path_beneath_attr path = {
        .allowed_access = handled,
        .parent_fd = compiler_fd,
    };
    if (syscall(
            __NR_landlock_add_rule,
            ruleset_fd,
            LANDLOCK_RULE_PATH_BENEATH,
            &path,
            0
        ) != 0) {
        close(compiler_fd);
        close(ruleset_fd);
        return fail("ADD_COMPILER_RULE", EXIT_SANDBOX_FAILURE);
    }
    close(compiler_fd);

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        close(ruleset_fd);
        return fail("NO_NEW_PRIVS", EXIT_SANDBOX_FAILURE);
    }
    if (syscall(__NR_landlock_restrict_self, ruleset_fd, 0) != 0) {
        close(ruleset_fd);
        return fail("RESTRICT_SELF", EXIT_SANDBOX_FAILURE);
    }
    close(ruleset_fd);

    execve(argv[1], &argv[1], envp);
    return fail("EXEC_COMPILER", EXIT_SANDBOX_FAILURE);
#endif
}
