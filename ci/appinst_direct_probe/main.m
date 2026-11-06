#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <spawn.h>
#import <sys/stat.h>
#import <sys/wait.h>
#import <signal.h>
#import <errno.h>
#import <string.h>
#import <unistd.h>

extern char **environ;

/*
 * Single-purpose independent iOS12 test of DIRECT posix_spawn for /usr/bin/appinst.
 *
 * The app never passes any IPA path and never uses a shell. Its ONLY
 * appinst invocation is "--help". Official appinst can clean old, inactive
 * appinst temporary session directories BEFORE parsing --help; the UI
 * explicitly tells the user before obtaining consent.
 */
static NSString *WRDescribeError(int error) {
    const char *message = strerror(error);
    return [NSString stringWithFormat:@"%d (%s)", error, message ? message : "?"];
}

static NSString *WRRunHelpProbe(void) {
    const char *binary = "/usr/bin/appinst";
    uid_t uid = getuid();
    uid_t euid = geteuid();
    NSMutableString *report = [NSMutableString stringWithFormat:
        @"WebReader • Teste direto appinst\niOS: %@\nUID: %u | EUID: %u\nDestino: /usr/bin/appinst\nArgumento: --help (nenhuma IPA)\n",
         [UIDevice currentDevice].systemVersion, (unsigned)uid, (unsigned)euid];

    if (![[NSBundle mainBundle].bundleIdentifier
            isEqualToString:@"com.example.WebReaderAppinstDirectProbe"]) {
        [report appendString:@"RESULTADO: build de teste incorreta. Nenhuma execução.\n"];
        return report;
    }
    if (euid == 0) {
        [report appendString:@"RESULTADO: execução como root recusada.\n"];
        return report;
    }
    // Read-only metadata probes are advisory: iOS sandbox may deny lstat
    // even when posix_spawn is a distinct operation. Do NOT return early
    // on EPERM. Only direct spawn can determine launch permission.
    struct stat st;
    if (lstat(binary, &st) != 0) {
        [report appendFormat:@"Diagnóstico lstat: %@ (não conclusivo)\n",
         WRDescribeError(errno)];
    } else if (!S_ISREG(st.st_mode)) {
        [report appendString:@"RESULTADO: destino visível, mas não é arquivo regular.\n"];
        return report;
    } else {
        [report appendString:@"Diagnóstico lstat: arquivo regular\n"];
    }
    if (access(binary, X_OK) != 0) {
        [report appendFormat:@"Diagnóstico access(X_OK): %@ (não conclusivo)\n",
         WRDescribeError(errno)];
    } else {
        [report appendString:@"Diagnóstico access(X_OK): permitido\n"];
    }
    [report appendString:@"Tentando posix_spawn diretamente (--help somente)...\n"];
    char * const arguments[] = {
        (char *)"/usr/bin/appinst", (char *)"--help", NULL
    };
    pid_t child = -1;
    int rc = posix_spawn(&child, binary, NULL, NULL, arguments, environ);
    if (rc != 0 || child <= 0) {
        [report appendFormat:@"RESULTADO: posix_spawn BLOQUEADO: %@\n",
         WRDescribeError(rc != 0 ? rc : ECHILD)];
        [report appendString:@"Nenhuma IPA instalada. Próxima opção: ponte Chimera.\n"];
        return report;
    }
    [report appendFormat:@"RESULTADO: posix_spawn ACEITO. PID: %d\n", child];

    int status = 0;
    for (int attempt = 0; attempt < 80; ++attempt) {
        pid_t finished = waitpid(child, &status, WNOHANG);
        if (finished == child) {
            if (WIFEXITED(status)) {
                [report appendFormat:@"Processo encerrou, código: %d\n",
                 WEXITSTATUS(status)];
                [report appendString:@"Código não zero é esperado em appinst --help.\n"];
            } else if (WIFSIGNALED(status)) {
                [report appendFormat:@"Processo terminou por sinal: %d\n",
                 WTERMSIG(status)];
            } else {
                [report appendString:@"Processo encerrou sem status convencional.\n"];
            }
            [report appendString:@"Nenhuma IPA foi fornecida ao instalador.\n"];
            return report;
        }
        if (finished < 0) {
            [report appendFormat:@"waitpid indisponível: %@\n",
             WRDescribeError(errno)];
            [report appendString:@"Spawn foi aceito; não confirmou execução do help.\n"];
            return report;
        }
        usleep(100000);
    }
    (void)kill(child, SIGTERM);
    (void)waitpid(child, &status, 0);
    [report appendString:@"Tempo excedido: processo de ajuda encerrado.\n"];
    [report appendString:@"Não testar instalação até entender esse resultado.\n"];
    return report;
}

@interface WRAppinstProbeDelegate : UIResponder <UIApplicationDelegate>
@property (strong, nonatomic) UIWindow *window;
@end

@interface WRAppinstProbeController : UIViewController
@property (strong, nonatomic) UILabel *reportLabel;
@property (strong, nonatomic) UIButton *testButton;
@property (copy, nonatomic) NSString *report;
@end

@implementation WRAppinstProbeController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor whiteColor];
    self.title = @"WebReader appinst Test";
    self.report = @"Este app só verifica se o WebReader pode executar /usr/bin/appinst diretamente.\nNenhuma IPA será instalada.";
    UILabel *label = [[UILabel alloc] initWithFrame:CGRectZero];
    label.numberOfLines = 0;
    label.textColor = [UIColor blackColor];
    label.font = [UIFont systemFontOfSize:15];
    label.textAlignment = NSTextAlignmentLeft;
    label.translatesAutoresizingMaskIntoConstraints = NO;
    label.text = self.report;
    self.reportLabel = label;
    [self.view addSubview:label];

    UIButton *test = [UIButton buttonWithType:UIButtonTypeSystem];
    [test setTitle:@"Testar appinst diretamente" forState:UIControlStateNormal];
    test.titleLabel.font = [UIFont boldSystemFontOfSize:17];
    test.translatesAutoresizingMaskIntoConstraints = NO;
    [test addTarget:self action:@selector(confirmTest)
     forControlEvents:UIControlEventTouchUpInside];
    self.testButton = test;
    [self.view addSubview:test];

    UIButton *copy = [UIButton buttonWithType:UIButtonTypeSystem];
    [copy setTitle:@"Copiar resultado" forState:UIControlStateNormal];
    copy.translatesAutoresizingMaskIntoConstraints = NO;
    [copy addTarget:self action:@selector(copyReport)
    forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:copy];

    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [label.topAnchor constraintEqualToAnchor:safe.topAnchor constant:28],
        [label.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:20],
        [label.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-20],
        [test.topAnchor constraintEqualToAnchor:label.bottomAnchor constant:24],
        [test.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:20],
        [test.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-20],
        [test.heightAnchor constraintEqualToConstant:50],
        [copy.topAnchor constraintEqualToAnchor:test.bottomAnchor constant:16],
        [copy.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [copy.heightAnchor constraintEqualToConstant:44]
    ]];
}

- (void)confirmTest {
    UIAlertController *alert = [UIAlertController
        alertControllerWithTitle:@"Testar appinst --help?"
        message:@"Este teste NÃO instala aplicativos. O appinst oficial pode limpar arquivos temporários de sessões antigas antes de exibir a ajuda. Não execute durante outra instalação. Deseja continuar?"
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancelar"
        style:UIAlertActionStyleCancel handler:nil]];
    __weak WRAppinstProbeController *weakSelf = self;
    [alert addAction:[UIAlertAction actionWithTitle:@"Executar teste"
        style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
            (void)action;
            WRAppinstProbeController *strongSelf = weakSelf;
            if (!strongSelf) return;
            strongSelf.testButton.enabled = NO;
            strongSelf.report = @"Executando teste de ajuda... nenhuma IPA fornecida.";
            strongSelf.reportLabel.text = strongSelf.report;
            dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
                NSString *result = WRRunHelpProbe();
                dispatch_async(dispatch_get_main_queue(), ^{
                    WRAppinstProbeController *owner = weakSelf;
                    if (!owner) return;
                    owner.report = result;
                    owner.reportLabel.text = result;
                    owner.testButton.enabled = YES;
                });
            });
        }]];
    [self presentViewController:alert animated:YES completion:nil];
}

- (void)copyReport {
    [UIPasteboard generalPasteboard].string = self.report ?: @"";
    UIAlertController *alert = [UIAlertController
        alertControllerWithTitle:@"Relatório copiado"
        message:@"Cole o resultado no chat para decidirmos se a ponte Chimera é necessária."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK"
        style:UIAlertActionStyleDefault handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
@end

@implementation WRAppinstProbeDelegate
- (BOOL)application:(UIApplication *)application
  didFinishLaunchingWithOptions:(NSDictionary *)launchOptions {
    (void)application;
    (void)launchOptions;
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[WRAppinstProbeController alloc] init];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char *argv[]) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil,
            NSStringFromClass([WRAppinstProbeDelegate class]));
    }
}
