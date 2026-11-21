#import <UIKit/UIKit.h>
#import <dlfcn.h>
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

static NSString *observeControl(int pid, int fd) {
    proc_name_fn name = (proc_name_fn)dlsym(RTLD_DEFAULT, "proc_name");
    proc_info_fn info = (proc_info_fn)dlsym(RTLD_DEFAULT, "proc_pidinfo");
    if (!name || !info) return @"API_UNAVAILABLE";

    char executable[256] = {0};
    if (name(pid, executable, sizeof(executable)) <= 0 ||
        strncmp(executable, "WRFDTarget", sizeof(executable)) != 0)
        return @"TARGET_UNCONFIRMED";

    struct fd_record records[1024];
    int size = info(pid, 1, 0, records, sizeof(records));
    memset(executable, 0, sizeof(executable));
    if (name(pid, executable, sizeof(executable)) <= 0 ||
        strncmp(executable, "WRFDTarget", sizeof(executable)) != 0)
        return @"TARGET_UNCONFIRMED";
    if (size <= 0 || size > (int)sizeof(records) ||
        size % (int)sizeof(records[0]) != 0)
        return @"QUERY_UNAVAILABLE";
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
    self.report.text = [@"WR_PEER_FD=" stringByAppendingString:
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
