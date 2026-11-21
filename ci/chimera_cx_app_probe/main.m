#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <unistd.h>
#import "cx_client.h"

/*
 * Standalone iOS 12 CX transport laboratory.
 * No WebReader libraries, SQLite, downloads, URL fetching, scripts, AppInst,
 * helper executable, privileged entitlement or installation command.
 * User presses a button before sending ONLY WRCHK2\n to loopback.
 */
static NSString *WRDAStatusText(WR_DA_Result status) {
    switch (status) {
        case WR_DA_NOTE:
            return @"WR_DA=NOTICE_ACCEPTED\n"
                    @"Servico CX respondeu. Nenhuma Release consultada; nenhuma IPA instalada.";
        case WR_DA_RATE:
            return @"WR_DA=RATE_LIMITED\n"
                    @"Limite de frequencia do CX. Nenhuma instalacao.";
        case WR_DA_DENY:
            return @"WR_DA=DENIED\n"
                    @"O servico CX rejeitou o aviso. Nenhuma instalacao.";
        case WR_DA_UNAVAILABLE:
            return @"WR_DA=UNAVAILABLE\n"
                    @"Servico CX indisponivel na porta 38973. Nenhuma instalacao.";
        case WR_DA_BAD_RESPONSE:
            return @"WR_DA=PROTOCOL_REJECTED\n"
                    @"Resposta incompleta, desconhecida ou com bytes extras.";
        case WR_DA_TRANSPORT_ERROR:
        default:
            return @"WR_DA=TRANSPORT_ERROR\n"
                    @"Falha de comunicacao local. Nenhuma instalacao.";
    }
}

@interface WRDACtrl : UIViewController
@property (nonatomic, strong) UITextView *reportView;
@property (nonatomic, strong) UIButton *probeButton;
@property (nonatomic, copy) NSString *report;
@end

@implementation WRDACtrl

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor whiteColor];
    self.title = @"CX Sandbox QA";
    UILabel *description = [[UILabel alloc] initWithFrame:CGRectZero];
    description.translatesAutoresizingMaskIntoConstraints = NO;
    description.numberOfLines = 0;
    description.font = [UIFont systemFontOfSize:16];
    description.text = @"Teste isolado do servico CX em 127.0.0.1:38973.\n"
                        @"Nao busca releases, nao instala IPAs e nao altera o WebReader.";
    [self.view addSubview:description];

    UIButton *test = [UIButton buttonWithType:UIButtonTypeSystem];
    test.translatesAutoresizingMaskIntoConstraints = NO;
    test.titleLabel.font = [UIFont boldSystemFontOfSize:17];
    [test setTitle:@"Testar comunicacao CX" forState:UIControlStateNormal];
    [test addTarget:self action:@selector(startProbe)
       forControlEvents:UIControlEventTouchUpInside];
    self.probeButton = test;
    [self.view addSubview:test];

    UITextView *text = [[UITextView alloc] initWithFrame:CGRectZero];
    text.translatesAutoresizingMaskIntoConstraints = NO;
    text.editable = NO;
    text.selectable = YES;
    text.font = [UIFont monospacedSystemFontOfSize:14 weight:UIFontWeightRegular];
    text.layer.borderColor = [UIColor lightGrayColor].CGColor;
    text.layer.borderWidth = 1;
    text.layer.cornerRadius = 8;
    self.reportView = text;
    [self.view addSubview:text];

    UIButton *copy = [UIButton buttonWithType:UIButtonTypeSystem];
    copy.translatesAutoresizingMaskIntoConstraints = NO;
    [copy setTitle:@"Copiar relatorio" forState:UIControlStateNormal];
    [copy addTarget:self action:@selector(copyReport)
   forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:copy];

    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [description.topAnchor constraintEqualToAnchor:safe.topAnchor constant:20],
        [description.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:18],
        [description.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-18],
        [test.topAnchor constraintEqualToAnchor:description.bottomAnchor constant:22],
        [test.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [test.heightAnchor constraintGreaterThanOrEqualToConstant:44],
        [text.topAnchor constraintEqualToAnchor:test.bottomAnchor constant:18],
        [text.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:18],
        [text.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-18],
        [text.bottomAnchor constraintEqualToAnchor:copy.topAnchor constant:-12],
        [text.heightAnchor constraintGreaterThanOrEqualToConstant:140],
        [copy.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [copy.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-14],
        [copy.heightAnchor constraintGreaterThanOrEqualToConstant:44]
    ]];
    self.report = @"WR_DA=READY\n"
                   @"Pressione Testar comunicacao CX.\n"
                   @"Nenhuma solicitação e enviada automaticamente.";
    self.reportView.text = self.report;
}

- (void)startProbe {
    self.probeButton.enabled = NO;
    self.reportView.text = @"WR_DA=RUNNING\nAviso local somente leitura...";
    __weak typeof(self) weakSelf = self;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        WR_DA_Result result = wr_da_probe();
        NSString *report = [NSString stringWithFormat:
            @"WebReader CX Sandbox QA\n"
             @"Bundle: %@\n"
             @"iOS: %@\n"
             @"UID: %u | EUID: %u\n"
             @"Destino: 127.0.0.1:38973\n"
             @"Comando: WRCHK2 (7 bytes, LF)\n"
             @"%@\n"
             @"WR_DA_INSTALL=NEVER\n"
             @"WR_DA_PUBLISHER_AUTHENTICATED=NO\n",
             [[NSBundle mainBundle] bundleIdentifier] ?: @"unknown",
             [[UIDevice currentDevice] systemVersion],
             (unsigned)getuid(), (unsigned)geteuid(),
             WRDAStatusText(result)];
        dispatch_async(dispatch_get_main_queue(), ^{
            WRDACtrl *strongSelf = weakSelf;
            if (!strongSelf) return;
            strongSelf.report = report;
            strongSelf.reportView.text = report;
            strongSelf.probeButton.enabled = YES;
        });
    });
}

- (void)copyReport {
    [UIPasteboard generalPasteboard].string = self.report ?: @"";
}
@end

@interface WRDAAppDelegate : UIResponder <UIApplicationDelegate>
@property (nonatomic, strong) UIWindow *window;
@end

@implementation WRDAAppDelegate
- (BOOL)application:(UIApplication *)application
    didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    (void)application;
    (void)launchOptions;
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[UINavigationController alloc]
        initWithRootViewController:[[WRDACtrl alloc] init]];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char **argv) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil,
            NSStringFromClass([WRDAAppDelegate class]));
    }
}
