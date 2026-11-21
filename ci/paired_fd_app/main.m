#import <UIKit/UIKit.h>
#import <dlfcn.h>
#import <errno.h>
#import <signal.h>
#import <fcntl.h>
#import <limits.h>
#import <stdint.h>
#import <string.h>
#import <unistd.h>

#ifndef WR_FD_TARGET
struct fd_record {
    int32_t fd;
    uint32_t type;
};
typedef int (*proc_name_fn)(int, void *, uint32_t);
typedef int (*proc_info_fn)(int, int, uint64_t, void *, int);

static NSString *targetNameFailure(proc_name_fn name, int pid, NSString *stage) {
    char executable[256] = {0};
    errno = 0;
    int length = name(pid, executable, sizeof(executable));
    int nameError = errno;
    if (length > 0) {
        if (strncmp(executable, "WRFDTarget", sizeof(executable)) == 0) return nil;
        return [NSString stringWithFormat:@"%@_NAME_MISMATCH", stage];
    }

    // Signal 0 only checks existence/permission, without delivering a signal.
    errno = 0;
    int live = kill(pid, 0);
    int liveError = errno;
    NSString *pidState = @"UNKNOWN";
    if (live == 0 || liveError == EPERM) pidState = @"PRESENT";
    if (live < 0 && liveError == ESRCH) pidState = @"NOT_FOUND";
    errno = 0;
    int selfLength = name(getpid(), executable, sizeof(executable));
    return [NSString stringWithFormat:@"%@_NAME_UNAVAILABLE_ERRNO_%d_PID_%@_SELF_%@",
            stage, nameError, pidState, selfLength > 0 ? @"OK" : @"UNAVAILABLE"];
}

static NSString *observeControl(int pid, int fd) {
    proc_name_fn name = (proc_name_fn)dlsym(RTLD_DEFAULT, "proc_name");
    proc_info_fn info = (proc_info_fn)dlsym(RTLD_DEFAULT, "proc_pidinfo");
    if (!name) return @"NAME_API_UNAVAILABLE";
    if (!info) return @"FD_API_UNAVAILABLE";

    NSString *failure = targetNameFailure(name, pid, @"BEFORE");
    if (failure) return failure;

    struct fd_record records[1024];
    errno = 0;
    int size = info(pid, 1, 0, records, sizeof(records));
    int queryError = errno;
    failure = targetNameFailure(name, pid, @"AFTER");
    if (failure) return failure;
    if (size <= 0)
        return [NSString stringWithFormat:@"FD_QUERY_UNAVAILABLE_ERRNO_%d", queryError];
    if (size > (int)sizeof(records) || size % (int)sizeof(records[0]) != 0)
        return @"FD_QUERY_INVALID_LAYOUT";
    for (int i = 0; i < size / (int)sizeof(records[0]); i++) {
        if (records[i].fd == fd) return @"CONTROL_FD_NUMBER_LISTED";
    }
    return @"CONTROL_FD_NUMBER_NOT_OBSERVED";
}
#endif

@interface WRPairedFD : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
#ifndef WR_FD_TARGET
@property (strong, nonatomic) UITextField *input;
@property (strong, nonatomic) UILabel *report;
#endif
@end

@implementation WRPairedFD
#ifndef WR_FD_TARGET
- (void)runProbe {
    NSArray<NSString *> *parts = [(self.input.text ?: @"") componentsSeparatedByString:@":"];
    if (parts.count != 2) {
        self.report.text = @"Digite o código PID:FD exibido no app alvo.";
        return;
    }
    NSScanner *pidScanner = [NSScanner scannerWithString:parts[0]];
    NSScanner *fdScanner = [NSScanner scannerWithString:parts[1]];
    pidScanner.charactersToBeSkipped = nil;
    fdScanner.charactersToBeSkipped = nil;
    long long pid = 0, fd = 0;
    if (![pidScanner scanLongLong:&pid] || !pidScanner.isAtEnd ||
        ![fdScanner scanLongLong:&fd] || !fdScanner.isAtEnd ||
        pid <= 1 || pid > INT_MAX || fd < 0 || fd > INT_MAX) {
        self.report.text = @"Digite o código PID:FD exibido no app alvo.";
        return;
    }
    [self.input resignFirstResponder];
    self.report.text = [@"WR_PEER_FD_V2=" stringByAppendingString:
                        observeControl((int)pid, (int)fd)];
}
#endif

- (BOOL)application:(UIApplication *)application
    didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    (void)application;
    (void)launchOptions;
    UIViewController *controller = [[UIViewController alloc] init];
    controller.view.backgroundColor = UIColor.whiteColor;
    UILabel *report = [[UILabel alloc] init];
    report.textColor = UIColor.blackColor;
    report.numberOfLines = 0;
    report.textAlignment = NSTextAlignmentCenter;
    UIStackView *stack = [[UIStackView alloc] init];
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 16;
    [stack addArrangedSubview:report];
#ifdef WR_FD_TARGET
    // Keep this descriptor open for the life of this isolated test app.
    int control = open("/dev/null", O_RDONLY);
    report.text = control < 0 ? @"WR_PEER_TARGET=CONTROL_UNAVAILABLE" :
        [NSString stringWithFormat:@"Código de teste\n\n%d:%d\n\nTroque de app sem encerrar este.", getpid(), control];
#else
    self.report = report;
    report.text = @"Digite o código exibido no WebReader FD Alvo.";
    self.input = [[UITextField alloc] init];
    self.input.borderStyle = UITextBorderStyleRoundedRect;
    self.input.placeholder = @"PID:FD";
    self.input.keyboardType = UIKeyboardTypeNumbersAndPunctuation;
    [stack addArrangedSubview:self.input];
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button setTitle:@"Consultar descritor de teste" forState:UIControlStateNormal];
    [button addTarget:self action:@selector(runProbe) forControlEvents:UIControlEventTouchUpInside];
    [stack addArrangedSubview:button];
#endif
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    [controller.view addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:controller.view.leadingAnchor constant:24],
        [stack.trailingAnchor constraintEqualToAnchor:controller.view.trailingAnchor constant:-24],
        [stack.centerYAnchor constraintEqualToAnchor:controller.view.centerYAnchor],
    ]];
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass(WRPairedFD.class));
    }
}
