#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>

/*
 * Separate, disposable iOS12 app ONLY for testing a real appinst v1->v2
 * overwrite and persistence of one NSUserDefaults key.
 * Never embeds WebReader code, accounts, content, Library or chapters.
 */
@interface WRDisposableAppDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end

@implementation WRDisposableAppDelegate
- (BOOL)application:(UIApplication *)application
    didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    (void)application;
    (void)launchOptions;
    NSUserDefaults *store = [NSUserDefaults standardUserDefaults];
    NSString *marker = [store stringForKey:@"webreader-appinst-disposable-data"];
    BOOL restored = (marker != nil);
    if (!restored) {
        marker = @"WR-DISPOSABLE-SAVED-V1";
        [store setObject:marker forKey:@"webreader-appinst-disposable-data"];
        [store synchronize];
    }
    NSString *version = [[NSBundle mainBundle] objectForInfoDictionaryKey:@"CFBundleVersion"];
    BOOL preserved = [version isEqualToString:@"2"] &&
        [marker isEqualToString:@"WR-DISPOSABLE-SAVED-V1"];
    NSString *result = preserved ?
        @"SIM - registro preservado após atualização." :
        ([version isEqualToString:@"2"] ?
            @"NÃO - registro inicial não encontrado." :
            @"Versão 1: registro local criado para teste.");
    NSString *body = [NSString stringWithFormat:
        @"APP DESCARTÁVEL - NÃO É O WEBREADER\n\n"
         "Versão instalada: %@\n\n"
         "Registro salvo: %@\n\n"
         "Persistência dos dados: %@\n\n"
         "Não há rede, login, Biblioteca ou conteúdo.",
        version, marker, result];
    UIViewController *controller = [[UIViewController alloc] init];
    controller.view.backgroundColor = [UIColor whiteColor];
    UILabel *label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.text = body;
    label.textColor = [UIColor blackColor];
    label.numberOfLines = 0;
    label.font = [UIFont systemFontOfSize:17];
    label.textAlignment = NSTextAlignmentCenter;
    label.translatesAutoresizingMaskIntoConstraints = NO;
    [controller.view addSubview:label];
    [NSLayoutConstraint activateConstraints:@[
        [label.leadingAnchor constraintEqualToAnchor:controller.view.leadingAnchor constant:20],
        [label.trailingAnchor constraintEqualToAnchor:controller.view.trailingAnchor constant:-20],
        [label.centerYAnchor constraintEqualToAnchor:controller.view.centerYAnchor]
    ]];
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil,
                                 NSStringFromClass([WRDisposableAppDelegate class]));
    }
}
