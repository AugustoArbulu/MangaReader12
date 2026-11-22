/*
 * WebReader Build70 Phase CV - read-only iOS12 LSApplicationWorkspace ABI probe.
 *
 * The executable only LOOKS UP an Objective-C class/method/encoding.
 * It DOES NOT create a workspace instance, send any selector to it, install,
 * invoke appinst, open an IPA, copy files, request privileges or access a key.
 *
 * A method existing at runtime DOES NOT imply that the process is entitled
 * to call it, or that a verified file survives the handoff to installd.
 * This file is compile-only in CI; no IPA/DEB or executable is distributed.
 */
#include <objc/runtime.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdbool.h>

static void print_report(Class cls, Method method) {
    const unsigned count = method ? method_getNumberOfArguments(method) : 0u;
    const char *types = method ? method_getTypeEncoding(method) : NULL;
    const bool returns_bool = types && (types[0] == 'B' || types[0] == 'c');
    printf("CV_CLASS=%s\n", cls ? "PRESENT" : "ABSENT");
    printf("CV_SELECTOR=%s\n", method ? "PRESENT" : "ABSENT");
    printf("CV_ARG_COUNT=%u\n", count);
    printf("CV_BOOL_RETURN=%s\n", method ? (returns_bool ? "YES" : "NO") : "UNKNOWN");
    printf("CV_CALL=NOT_ATTEMPTED\n");
    printf("CV_AUTHORIZATION=DENIED\n");
    printf("CV_INSTALLATION=NOT_ATTEMPTED\n");
}

int main(void) {
    Class cls = objc_lookUpClass("LSApplicationWorkspace");
    if (!cls) {
        /* Load only the system metadata framework to discover its classes. */
        void *framework = dlopen(
            "/System/Library/Frameworks/MobileCoreServices.framework/MobileCoreServices",
            RTLD_LAZY | RTLD_LOCAL
        );
        (void)framework;
        cls = objc_lookUpClass("LSApplicationWorkspace");
    }
    Method method = NULL;
    if (cls) {
        SEL selector = sel_registerName("installApplication:withOptions:error:");
        method = class_getInstanceMethod(cls, selector);
    }
    print_report(cls, method);
    return 0;
}
