#import <UIKit/UIKit.h>
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <unistd.h>

/*
 * DB4: sandboxed iOS12 one-shot GitHub API HTTPS diagnostics.
 * Separate Bundle ID and application. No WebReader code, no installer,
 * privileged tool, IPA, release asset, local files or background operation.
 * One explicit user button causes ONE GET to the fixed GitHub API endpoint.
 * As soon as headers arrive, abort the body (URLSessionResponseCancel).
 * HTTP status is transport evidence, NOT publisher authentication.
 */
static NSString *const WRDB4Endpoint =
    @"https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest";

static NSString *WRDB4SafeHeader(NSHTTPURLResponse *response, NSString *key) {
    for (id headerKey in response.allHeaderFields) {
        if (![headerKey isKindOfClass:[NSString class]]) continue;
        if ([[(NSString *)headerKey lowercaseString] isEqualToString:key]) {
            id raw = response.allHeaderFields[headerKey];
            if (![raw isKindOfClass:[NSString class]] &&
                ![raw isKindOfClass:[NSNumber class]]) return @"MISSING";
            NSString *value = [raw description];
            // Never echo long/untrusted values or injected newlines.
            value = [[value componentsSeparatedByCharactersInSet:
                [NSCharacterSet newlineCharacterSet]] firstObject];
            if (value.length > 72) value = [value substringToIndex:72];
            return value.length > 0 ? value : @"EMPTY";
        }
    }
    return @"MISSING";
}

@interface WRDB4HTTPSProbe : NSObject <NSURLSessionDataDelegate, NSURLSessionTaskDelegate>
@property (nonatomic, strong) NSURLSession *session;
@property (nonatomic, strong) NSURLSessionDataTask *task;
@property (nonatomic, copy) void (^callback)(NSString *);
@property (nonatomic, assign) BOOL finished;
- (void)start:(void (^)(NSString *))completion;
@end

@implementation WRDB4HTTPSProbe

- (void)finish:(NSString *)message {
    void (^callback)(NSString *) = nil;
    @synchronized(self) {
        if (self.finished) return;
        self.finished = YES;
        callback = self.callback;
        self.callback = nil;
    }
    // Never cache, parse or persist a remote body.
    [self.session invalidateAndCancel];
    self.task = nil;
    self.session = nil;
    if (callback) callback(message);
}

- (void)start:(void (^)(NSString *))completion {
    self.callback = completion;
    if (geteuid() == 0) {
        [self finish:@"WR_DB4_ERROR=ROOT_NOT_ALLOWED"];
        return;
    }
    NSURL *url = [NSURL URLWithString:WRDB4Endpoint];
    NSURLSessionConfiguration *config =
        [NSURLSessionConfiguration ephemeralSessionConfiguration];
    config.URLCache = nil;
    config.URLCredentialStorage = nil;
    config.HTTPCookieStorage = nil;
    config.requestCachePolicy = NSURLRequestReloadIgnoringLocalCacheData;
    config.timeoutIntervalForRequest = 12;
    config.timeoutIntervalForResource = 18;
    config.HTTPMaximumConnectionsPerHost = 1;
    self.session = [NSURLSession sessionWithConfiguration:config
        delegate:self delegateQueue:nil];

    NSMutableURLRequest *request =
        [NSMutableURLRequest requestWithURL:url
            cachePolicy:NSURLRequestReloadIgnoringLocalCacheData
            timeoutInterval:12];
    request.HTTPMethod = @"GET";
    [request setValue:@"application/vnd.github+json" forHTTPHeaderField:@"Accept"];
    [request setValue:@"WebReader-iOS12-DB4-ReadOnlyQA"
        forHTTPHeaderField:@"User-Agent"];
    self.task = [self.session dataTaskWithRequest:request];
    [self.task resume];
}

- (void)URLSession:(NSURLSession *)session task:(NSURLSessionTask *)task
    willPerformHTTPRedirection:(NSHTTPURLResponse *)response
    newRequest:(NSURLRequest *)request
    completionHandler:(void (^)(NSURLRequest *))completionHandler {
    (void)session; (void)task; (void)response; (void)request;
    // Do not follow any redirect, including other GitHub hosts.
    completionHandler(nil);
    [self finish:@"WR_DB4_REDIRECT=DENIED\nWR_DB4_HTTP_REACHED=YES"];
}

- (void)URLSession:(NSURLSession *)session
    dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveResponse:(NSURLResponse *)response
    completionHandler:(void (^)(NSURLSessionResponseDisposition))completionHandler {
    (void)session; (void)dataTask;
    completionHandler(NSURLSessionResponseCancel);
    if (![response isKindOfClass:[NSHTTPURLResponse class]] ||
        ![response.URL.absoluteString isEqualToString:WRDB4Endpoint]) {
        [self finish:@"WR_DB4_HTTP_REACHED=NO\nWR_DB4_ERROR=UNEXPECTED_RESPONSE_URL"];
        return;
    }
    NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
    NSString *details = [NSString stringWithFormat:
        @"WR_DB4_HTTP_REACHED=YES\n"
         @"WR_DB4_HTTP_STATUS=%ld\n"
         @"WR_DB4_CONTENT_TYPE=%@\n"
         @"WR_DB4_RATELIMIT_REMAINING=%@\n"
         @"WR_DB4_RATELIMIT_LIMIT=%@\n"
         @"WR_DB4_RATELIMIT_RESOURCE=%@\n"
         @"WR_DB4_RETRY_AFTER=%@\n"
         @"WR_DB4_SERVER=%@\n"
         @"WR_DB4_HTTP_RESPONSE_BODY=NOT_READ\n",
         (long)http.statusCode,
         WRDB4SafeHeader(http, @"content-type"),
         WRDB4SafeHeader(http, @"x-ratelimit-remaining"),
         WRDB4SafeHeader(http, @"x-ratelimit-limit"),
         WRDB4SafeHeader(http, @"x-ratelimit-resource"),
         WRDB4SafeHeader(http, @"retry-after"),
         WRDB4SafeHeader(http, @"server")];
    [self finish:details];
}

- (void)URLSession:(NSURLSession *)session
    task:(NSURLSessionTask *)task
    didCompleteWithError:(NSError *)error {
    (void)session; (void)task;
    NSString *message = error
        ? [NSString stringWithFormat:@"WR_DB4_HTTP_REACHED=NO\n"
                @"WR_DB4_ERROR_DOMAIN=%@\nWR_DB4_ERROR_CODE=%ld",
                error.domain, (long)error.code]
        : @"WR_DB4_HTTP_REACHED=NO\nWR_DB4_ERROR=NO_HEADERS";
    [self finish:message];
}

@end

@interface WRDB4Controller : UIViewController
@property (nonatomic, strong) UITextView *reportView;
@property (nonatomic, strong) UIButton *button;
@property (nonatomic, strong) WRDB4HTTPSProbe *activeProbe;
@property (nonatomic, copy) NSString *report;
@end

@implementation WRDB4Controller

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor whiteColor];
    self.title = @"GitHub HTTPS QA";

    UILabel *intro = [[UILabel alloc] initWithFrame:CGRectZero];
    intro.translatesAutoresizingMaskIntoConstraints = NO;
    intro.numberOfLines = 0;
    intro.font = [UIFont systemFontOfSize:15];
    intro.text = @"Teste HTTPS isolado no iOS 12. Uma consulta GET ao GitHub, "
                  @"somente para ler o status HTTP e cabecalhos. "
                  @"Nao baixa o corpo, nao verifica publisher nem instala IPA.";
    [self.view addSubview:intro];

    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    button.translatesAutoresizingMaskIntoConstraints = NO;
    button.titleLabel.font = [UIFont boldSystemFontOfSize:17];
    [button setTitle:@"Testar HTTPS GitHub" forState:UIControlStateNormal];
    [button addTarget:self action:@selector(runProbe)
        forControlEvents:UIControlEventTouchUpInside];
    self.button = button;
    [self.view addSubview:button];

    UITextView *results = [[UITextView alloc] initWithFrame:CGRectZero];
    results.translatesAutoresizingMaskIntoConstraints = NO;
    results.font = [UIFont fontWithName:@"Menlo-Regular" size:13] ?:
                   [UIFont systemFontOfSize:13];
    results.editable = NO;
    results.selectable = YES;
    results.layer.borderWidth = 1;
    results.layer.borderColor = [UIColor lightGrayColor].CGColor;
    self.reportView = results;
    [self.view addSubview:results];

    UIButton *copy = [UIButton buttonWithType:UIButtonTypeSystem];
    copy.translatesAutoresizingMaskIntoConstraints = NO;
    [copy setTitle:@"Copiar relatorio" forState:UIControlStateNormal];
    [copy addTarget:self action:@selector(copyResult)
        forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:copy];

    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    [NSLayoutConstraint activateConstraints:@[
        [intro.topAnchor constraintEqualToAnchor:safe.topAnchor constant:18],
        [intro.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:16],
        [intro.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-16],
        [button.topAnchor constraintEqualToAnchor:intro.bottomAnchor constant:16],
        [button.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [button.heightAnchor constraintGreaterThanOrEqualToConstant:44],
        [results.topAnchor constraintEqualToAnchor:button.bottomAnchor constant:12],
        [results.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor constant:16],
        [results.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor constant:-16],
        [results.bottomAnchor constraintEqualToAnchor:copy.topAnchor constant:-8],
        [results.heightAnchor constraintGreaterThanOrEqualToConstant:130],
        [copy.centerXAnchor constraintEqualToAnchor:safe.centerXAnchor],
        [copy.heightAnchor constraintGreaterThanOrEqualToConstant:44],
        [copy.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor constant:-10]
    ]];

    self.report = @"WR_DB4=READY\nNenhuma rede antes de tocar no botao.";
    self.reportView.text = self.report;
}

- (void)runProbe {
    if (self.activeProbe) return;
    self.button.enabled = NO;
    self.reportView.text = @"WR_DB4=RUNNING\nConsultando cabecalhos...";
    WRDB4HTTPSProbe *probe = [[WRDB4HTTPSProbe alloc] init];
    self.activeProbe = probe;
    __weak typeof(self) weakSelf = self;
    [probe start:^(NSString *observation) {
        dispatch_async(dispatch_get_main_queue(), ^{
            WRDB4Controller *strongSelf = weakSelf;
            if (!strongSelf) return;
            strongSelf.report = [NSString stringWithFormat:
                @"WebReader DB4 HTTPS QA\n"
                 @"Bundle=%@\n"
                 @"iOS=%@\n"
                 @"UID=%u EUID=%u\n"
                 @"Origin=%@\n"
                 @"%@\n"
                 @"WR_DB4_PUBLISHER_AUTHENTICATED=NO\n"
                 @"WR_DB4_IPA_DOWNLOADED=NO\n"
                 @"WR_DB4_INSTALL=NEVER\n",
                 [NSBundle mainBundle].bundleIdentifier ?: @"unknown",
                 [UIDevice currentDevice].systemVersion,
                 (unsigned)getuid(), (unsigned)geteuid(),
                 WRDB4Endpoint, observation];
            strongSelf.reportView.text = strongSelf.report;
            strongSelf.activeProbe = nil;
            strongSelf.button.enabled = YES;
        });
    }];
}

- (void)copyResult {
    [UIPasteboard generalPasteboard].string = self.report ?: @"";
}
@end

@interface WRDB4Delegate : UIResponder <UIApplicationDelegate>
@property (nonatomic, strong) UIWindow *window;
@end

@implementation WRDB4Delegate
- (BOOL)application:(UIApplication *)application
    didFinishLaunchingWithOptions:(NSDictionary *)options {
    (void)application; (void)options;
    self.window = [[UIWindow alloc] initWithFrame:[UIScreen mainScreen].bounds];
    self.window.rootViewController = [[UINavigationController alloc]
        initWithRootViewController:[[WRDB4Controller alloc] init]];
    [self.window makeKeyAndVisible];
    return YES;
}
@end

int main(int argc, char **argv) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil,
                                 NSStringFromClass([WRDB4Delegate class]));
    }
}
