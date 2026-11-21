#import <UIKit/UIKit.h>

extern const char *wr_self_fd_status(void);

@interface WRSelfFDDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end

@implementation WRSelfFDDelegate
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
    report.translatesAutoresizingMaskIntoConstraints = NO;
    report.text = [NSString stringWithFormat:@"WebReader FD Teste\n\n%@",
                   [NSString stringWithUTF8String:wr_self_fd_status()]];
    [controller.view addSubview:report];
    [NSLayoutConstraint activateConstraints:@[
        [report.leadingAnchor constraintEqualToAnchor:controller.view.leadingAnchor constant:16],
        [report.trailingAnchor constraintEqualToAnchor:controller.view.trailingAnchor constant:-16],
        [report.centerYAnchor constraintEqualToAnchor:controller.view.centerYAnchor],
    ]];

    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass(WRSelfFDDelegate.class));
    }
}
