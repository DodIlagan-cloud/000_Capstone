// M1 - User Access Management Start
// Starts the Module 1 ASP.NET Core web frontend and exposes the Python API base URL to Razor pages.
using System.Diagnostics;
using System.Net;
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);
var centralRuntime = StatsCentralRuntime.Load(builder.Environment.ContentRootPath);
StatsLoggingBootstrap.Configure(builder, centralRuntime);
builder.Configuration.AddInMemoryCollection(centralRuntime.ConfigurationDefaults);

builder.Services.AddRazorPages();
builder.Services.AddHttpClient();
builder.Services.AddSingleton(centralRuntime);
builder.Services.AddCors(options =>
{
    options.AddPolicy(
        "StatsCorsPolicy",
        policy =>
        {
            if (centralRuntime.CorsAllowedOrigins.Count > 0)
            {
                policy.WithOrigins(centralRuntime.CorsAllowedOrigins.ToArray())
                    .AllowAnyHeader()
                    .AllowAnyMethod();
            }
        }
    );
});
builder.Services.AddSingleton(
    new StatsApiOptions(
        builder.Configuration["StatsApi:BaseUrl"]
            ?? Environment.GetEnvironmentVariable("STATS_API_BASE_URL")
            ?? string.Empty
    )
);
// M2 - Stats Web Shell Start
// Starts missing local sibling APIs so the local Stats shell behaves like one app.
builder.Services.Configure<StatsLocalOrchestrationOptions>(
    builder.Configuration.GetSection("StatsWeb:LocalOrchestration")
);
builder.Services.AddHostedService<StatsLocalServiceOrchestrator>();
// M2 End
// M13 - Containerization Start
// Keeps the browser on the single Stats Web entry point while proxying API calls to internal module processes.
builder.Services.AddSingleton(
    new StatsWebProxyOptions(
        IdentityBaseUrl: builder.Configuration["StatsWeb:Proxy:IdentityBaseUrl"] ?? centralRuntime.ModuleUrl("IDENTITY_PORT"),
        FileValidationBaseUrl: builder.Configuration["StatsWeb:Proxy:FileValidationBaseUrl"] ?? centralRuntime.ModuleUrl("FILE_VALIDATION_PORT"),
        FileIngestionBaseUrl: builder.Configuration["StatsWeb:Proxy:FileIngestionBaseUrl"] ?? centralRuntime.ModuleUrl("FILE_VALIDATION_PORT"),
        DocumentParsingBaseUrl: builder.Configuration["StatsWeb:Proxy:DocumentParsingBaseUrl"] ?? centralRuntime.ModuleUrl("DOCUMENT_PARSING_PORT"),
        TransactionExtractionBaseUrl: builder.Configuration["StatsWeb:Proxy:TransactionExtractionBaseUrl"] ?? centralRuntime.ModuleUrl("TRANSACTION_EXTRACTION_PORT"),
        DataValidationBaseUrl: builder.Configuration["StatsWeb:Proxy:DataValidationBaseUrl"] ?? centralRuntime.ModuleUrl("DATA_VALIDATION_PORT")
    )
);
// M13 End
// M2 - Stats Web Shell Start
// Exposes shell feature flags and deferred downstream module targets through configuration.
builder.Services.AddSingleton(
    new StatsWebShellOptions(
        UploadShellEnabled: builder.Configuration.GetValue("StatsWeb:Features:UploadShell", true),
        EmailIngestionSetupEnabled: builder.Configuration.GetValue("StatsWeb:Features:EmailIngestionSetup", true),
        DashboardShellEnabled: builder.Configuration.GetValue("StatsWeb:Features:DashboardShell", true),
        ReportsShellEnabled: builder.Configuration.GetValue("StatsWeb:Features:ReportsShell", true),
        FileValidationBaseUrl: builder.Configuration["StatsWeb:Downstream:FileValidationBaseUrl"] ?? string.Empty,
        FileIngestionBaseUrl: builder.Configuration["StatsWeb:Downstream:FileIngestionBaseUrl"] ?? string.Empty,
        DocumentParsingBaseUrl: builder.Configuration["StatsWeb:Downstream:DocumentParsingBaseUrl"] ?? string.Empty,
        TransactionExtractionBaseUrl: builder.Configuration["StatsWeb:Downstream:TransactionExtractionBaseUrl"] ?? string.Empty,
        DataValidationBaseUrl: builder.Configuration["StatsWeb:Downstream:DataValidationBaseUrl"] ?? string.Empty,
        EmailIngestionBaseUrl: builder.Configuration["StatsWeb:Downstream:EmailIngestionBaseUrl"] ?? string.Empty,
        StatsDataBaseUrl: builder.Configuration["StatsWeb:Downstream:StatsDataBaseUrl"] ?? string.Empty,
        ReportingEmbedConfigUrl: builder.Configuration["StatsWeb:Downstream:ReportingEmbedConfigUrl"] ?? string.Empty,
        PowerBiTenantId: builder.Configuration["StatsWeb:PowerBi:TenantId"] ?? string.Empty,
        PowerBiWorkspaceId: builder.Configuration["StatsWeb:PowerBi:WorkspaceId"] ?? string.Empty,
        PowerBiReportId: builder.Configuration["StatsWeb:PowerBi:DashboardReportId"] ?? string.Empty,
        FabricCapacityName: builder.Configuration["StatsWeb:Fabric:CapacityName"] ?? string.Empty,
        FabricWorkspaceName: builder.Configuration["StatsWeb:Fabric:WorkspaceName"] ?? string.Empty,
        AzureEnvironment: builder.Configuration["StatsWeb:Azure:Environment"] ?? "local",
        KeyVaultUri: builder.Configuration["StatsWeb:Azure:KeyVaultUri"] ?? string.Empty,
        UseManagedIdentity: builder.Configuration.GetValue("StatsWeb:Azure:UseManagedIdentity", false)
    )
);
// M2 End

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseStaticFiles();
app.UseRouting();
app.UseCors("StatsCorsPolicy");
app.UseMiddleware<StatsCorrelationMiddleware>();
// M13 - Containerization Start
// Browser API calls stay relative to Stats Web; this forwards them to the in-container module APIs.
app.MapMethods(
    "/api/v1/{**path}",
    ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    StatsWebApiProxy.ProxyApiRequestAsync
);
// M13 End
app.MapRazorPages();
// M13 - Containerization Start
// Exposes a /health endpoint so the M13 Compose health check and container startup script can verify Stats Web is ready.
app.MapGet("/health", () => Results.Ok(new { status = "healthy", service = "Stats Web" }));
// M13 End
app.Run();

public sealed record StatsApiOptions(string BaseUrl);
// M13 - Containerization Start
public sealed record StatsWebProxyOptions(
    string IdentityBaseUrl,
    string FileValidationBaseUrl,
    string FileIngestionBaseUrl,
    string DocumentParsingBaseUrl,
    string TransactionExtractionBaseUrl,
    string DataValidationBaseUrl
);
// M13 End
// M2 - Stats Web Shell Start
// Defines optional local process orchestration for standalone module APIs.
public sealed class StatsLocalOrchestrationOptions
{
    public bool Enabled { get; set; }

    public bool StartMissingServices { get; set; } = true;

    public int HealthCheckTimeoutSeconds { get; set; } = 2;

    public List<StatsLocalServiceOptions> Services { get; set; } = [];
}

public sealed class StatsLocalServiceOptions
{
    public string Name { get; set; } = string.Empty;

    public string HealthUrl { get; set; } = string.Empty;

    public string WorkingDirectory { get; set; } = string.Empty;

    public string Command { get; set; } = string.Empty;

    public string Arguments { get; set; } = string.Empty;

    public Dictionary<string, string> Environment { get; set; } = [];
}

public sealed class StatsLocalServiceOrchestrator(
    IConfiguration configuration,
    StatsCentralRuntime centralRuntime,
    IHttpClientFactory httpClientFactory,
    Microsoft.Extensions.Options.IOptions<StatsLocalOrchestrationOptions> options,
    ILogger<StatsLocalServiceOrchestrator> logger
) : IHostedService
{
    private readonly List<Process> startedProcesses = [];

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        var orchestrationOptions = options.Value;
        var azureEnvironment = configuration["StatsWeb:Azure:Environment"] ?? "local";
        if (!orchestrationOptions.Enabled || !IsLocalRuntime(azureEnvironment))
        {
            logger.LogInformation("Stats local orchestration is disabled for environment {Environment}.", azureEnvironment);
            return;
        }

        foreach (var service in orchestrationOptions.Services)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                return;
            }

            if (string.IsNullOrWhiteSpace(service.HealthUrl))
            {
                logger.LogWarning("Skipping local service {ServiceName}; no health URL is configured.", service.Name);
                continue;
            }

            if (await IsHealthyAsync(service, orchestrationOptions.HealthCheckTimeoutSeconds, cancellationToken))
            {
                logger.LogInformation("Local service {ServiceName} is already running.", service.Name);
                continue;
            }

            if (!orchestrationOptions.StartMissingServices)
            {
                logger.LogWarning("Local service {ServiceName} is not running and auto-start is disabled.", service.Name);
                continue;
            }

            StartService(service);
        }
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        foreach (var process in startedProcesses)
        {
            if (process.HasExited)
            {
                continue;
            }

            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch (Exception exception)
            {
                logger.LogWarning(exception, "Failed to stop local service process {ProcessId}.", process.Id);
            }
        }

        return Task.CompletedTask;
    }

    private static bool IsLocalRuntime(string azureEnvironment)
    {
        return string.Equals(azureEnvironment, "local", StringComparison.OrdinalIgnoreCase)
            || string.Equals(azureEnvironment, "development", StringComparison.OrdinalIgnoreCase);
    }

    private async Task<bool> IsHealthyAsync(
        StatsLocalServiceOptions service,
        int timeoutSeconds,
        CancellationToken cancellationToken
    )
    {
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromSeconds(Math.Max(1, timeoutSeconds)));

            var client = httpClientFactory.CreateClient();
            using var response = await client.GetAsync(service.HealthUrl, timeout.Token);
            return response.IsSuccessStatusCode;
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
        )
        {
            return false;
        }
    }

    private void StartService(StatsLocalServiceOptions service)
    {
        if (string.IsNullOrWhiteSpace(service.Command))
        {
            logger.LogWarning("Cannot start local service {ServiceName}; no command is configured.", service.Name);
            return;
        }

        var workingDirectory = ResolvePath(service.WorkingDirectory);
        var startInfo = new ProcessStartInfo
        {
            FileName = service.Command,
            Arguments = service.Arguments,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        foreach (var environmentVariable in service.Environment)
        {
            startInfo.Environment[environmentVariable.Key] = environmentVariable.Value;
        }

        try
        {
            var process = Process.Start(startInfo);
            if (process is null)
            {
                logger.LogWarning("Failed to start local service {ServiceName}.", service.Name);
                return;
            }

            startedProcesses.Add(process);
            logger.LogInformation("Started local service {ServiceName} as process {ProcessId}.", service.Name, process.Id);
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            logger.LogError(exception, "Failed to start local service {ServiceName}; verify the configured command exists.", service.Name);
        }
    }

    private string ResolvePath(string configuredPath)
    {
        if (string.IsNullOrWhiteSpace(configuredPath))
        {
            return centralRuntime.AppRoot;
        }

        return centralRuntime.ResolvePath(configuredPath);
    }
}
// M2 End
// M2 - Stats Web Shell Start
// Carries configurable shell readiness and future module endpoint settings.
public sealed record StatsWebShellOptions(
    bool UploadShellEnabled,
    bool EmailIngestionSetupEnabled,
    bool DashboardShellEnabled,
    bool ReportsShellEnabled,
    string FileValidationBaseUrl,
    string FileIngestionBaseUrl,
    string DocumentParsingBaseUrl,
    string TransactionExtractionBaseUrl,
    string DataValidationBaseUrl,
    string EmailIngestionBaseUrl,
    string StatsDataBaseUrl,
    string ReportingEmbedConfigUrl,
    string PowerBiTenantId,
    string PowerBiWorkspaceId,
    string PowerBiReportId,
    string FabricCapacityName,
    string FabricWorkspaceName,
    string AzureEnvironment,
    string KeyVaultUri,
    bool UseManagedIdentity
);
// M2 End
// M1 End

// M13 - Containerization Start
// Minimal reverse proxy for browser-originating API calls through the single Stats Web container port.
public static class StatsWebApiProxy
{
    public static async Task ProxyApiRequestAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions,
        ILoggerFactory loggerFactory
    )
    {
        var path = Convert.ToString(context.Request.RouteValues["path"]) ?? string.Empty;
        var targetBaseUrl = ResolveProxyBaseUrl(path, proxyOptions);
        if (string.IsNullOrWhiteSpace(targetBaseUrl))
        {
            context.Response.StatusCode = StatusCodes.Status404NotFound;
            await context.Response.WriteAsJsonAsync(new { detail = $"No Stats module route is configured for /api/v1/{path}." });
            return;
        }

        var targetUri = new Uri($"{targetBaseUrl.TrimEnd('/')}/api/v1/{path}{context.Request.QueryString}");
        using var requestMessage = new HttpRequestMessage(new HttpMethod(context.Request.Method), targetUri);

        foreach (var header in context.Request.Headers)
        {
            if (IsHopByHopHeader(header.Key) || string.Equals(header.Key, "Host", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (!requestMessage.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray()))
            {
                requestMessage.Content ??= new StreamContent(context.Request.Body);
                requestMessage.Content.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray());
            }
        }

        if (context.Request.ContentLength > 0 && requestMessage.Content is null)
        {
            requestMessage.Content = new StreamContent(context.Request.Body);
            if (!string.IsNullOrWhiteSpace(context.Request.ContentType))
            {
                requestMessage.Content.Headers.TryAddWithoutValidation("Content-Type", context.Request.ContentType);
            }
        }

        try
        {
            var client = httpClientFactory.CreateClient();
            client.Timeout = TimeSpan.FromMinutes(5);
            using var responseMessage = await client.SendAsync(
                requestMessage,
                HttpCompletionOption.ResponseHeadersRead,
                context.RequestAborted
            );

            context.Response.StatusCode = (int)responseMessage.StatusCode;
            foreach (var header in responseMessage.Headers)
            {
                if (!IsHopByHopHeader(header.Key))
                {
                    context.Response.Headers[header.Key] = header.Value.ToArray();
                }
            }

            foreach (var header in responseMessage.Content.Headers)
            {
                if (!IsHopByHopHeader(header.Key))
                {
                    context.Response.Headers[header.Key] = header.Value.ToArray();
                }
            }

            context.Response.Headers.Remove("transfer-encoding");
            await responseMessage.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
        )
        {
            var logger = loggerFactory.CreateLogger("StatsWebApiProxy");
            logger.LogWarning(exception, "Failed to proxy /api/v1/{Path} to configured Stats module target.", path);
            context.Response.StatusCode = StatusCodes.Status502BadGateway;
            await context.Response.WriteAsJsonAsync(new { detail = "Stats module API proxy request failed." });
        }
    }

    private static string ResolveProxyBaseUrl(string path, StatsWebProxyOptions proxyOptions)
    {
        if (path.StartsWith("auth", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("users", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.IdentityBaseUrl;
        }

        if (path.StartsWith("files/", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.FileValidationBaseUrl;
        }

        if (path.StartsWith("ingestions", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.FileIngestionBaseUrl;
        }

        if (path.StartsWith("parses", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.DocumentParsingBaseUrl;
        }

        if (path.StartsWith("extractions", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.TransactionExtractionBaseUrl;
        }

        if (path.StartsWith("validations", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.DataValidationBaseUrl;
        }

        return string.Empty;
    }

    private static bool IsHopByHopHeader(string headerName)
    {
        return string.Equals(headerName, "Connection", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Keep-Alive", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Proxy-Authenticate", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Proxy-Authorization", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "TE", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Trailer", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Transfer-Encoding", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Upgrade", StringComparison.OrdinalIgnoreCase);
    }
}
// M13 End

// M0 Architecture Hardening Start
// Loads the central runtime/path/logging registries before Stats Web wires services.
public sealed class StatsCentralRuntime
{
    public string AppRoot { get; private init; } = string.Empty;

    public string RuntimeConfigPath { get; private init; } = string.Empty;

    public string PathsConfigPath { get; private init; } = string.Empty;

    public string LoggingConfigPath { get; private init; } = string.Empty;

    public Dictionary<string, string> ModulePorts { get; private init; } = [];

    public Dictionary<string, string> LogicalPaths { get; private init; } = [];

    public Dictionary<string, string> LoggingDefaults { get; private init; } = [];

    public List<string> CorsAllowedOrigins { get; private init; } = [];

    public Dictionary<string, string?> ConfigurationDefaults { get; private set; } = [];

    public static StatsCentralRuntime Load(string contentRootPath)
    {
        var appRoot = ResolveAppRoot(contentRootPath);
        var runtimeConfigPath = ResolveConfigFile(
            Environment.GetEnvironmentVariable("STATS_RUNTIME_CONFIG"),
            appRoot,
            "config/stats.runtime.json"
        );
        var pathsConfigPath = ResolveConfigFile(
            Environment.GetEnvironmentVariable("STATS_PATHS_CONFIG"),
            appRoot,
            "config/stats.paths.json"
        );
        var loggingConfigPath = ResolveConfigFile(
            Environment.GetEnvironmentVariable("STATS_LOGGING_CONFIG"),
            appRoot,
            "config/stats.logging.json"
        );

        using var runtimeDocument = JsonDocument.Parse(File.ReadAllText(runtimeConfigPath));
        using var pathsDocument = JsonDocument.Parse(File.ReadAllText(pathsConfigPath));
        using var loggingDocument = JsonDocument.Parse(File.ReadAllText(loggingConfigPath));

        var runtimeRoot = runtimeDocument.RootElement;
        var ports = ReadDefaultMap(runtimeRoot.GetProperty("modulePorts"));
        var loggingDefaults = ReadDefaultMap(loggingDocument.RootElement.GetProperty("environmentVariables"));
        var corsAllowedOrigins = ReadCsv(
            Environment.GetEnvironmentVariable("CORS_ALLOWED_ORIGINS")
                ?? ReadDefault(runtimeRoot.GetProperty("network").GetProperty("CORS_ALLOWED_ORIGINS"))
        );
        var logicalPaths = ReadLogicalPaths(pathsDocument.RootElement, appRoot);

        var runtime = new StatsCentralRuntime
        {
            AppRoot = appRoot,
            RuntimeConfigPath = runtimeConfigPath,
            PathsConfigPath = pathsConfigPath,
            LoggingConfigPath = loggingConfigPath,
            ModulePorts = ports,
            LogicalPaths = logicalPaths,
            LoggingDefaults = loggingDefaults,
            CorsAllowedOrigins = corsAllowedOrigins,
        };

        runtime.ConfigurationDefaults = runtime.BuildConfigurationDefaults();
        return runtime;
    }

    public string ModuleUrl(string portKey)
    {
        if (!ModulePorts.TryGetValue(portKey, out var port) || string.IsNullOrWhiteSpace(port))
        {
            throw new InvalidOperationException($"Central runtime config is missing module port {portKey}.");
        }

        return $"http://localhost:{port}";
    }

    public string ResolvePath(string logicalOrConfiguredPath)
    {
        if (string.IsNullOrWhiteSpace(logicalOrConfiguredPath))
        {
            return AppRoot;
        }

        var path = LogicalPaths.TryGetValue(logicalOrConfiguredPath, out var logicalPath)
            ? logicalPath
            : logicalOrConfiguredPath;

        return Path.IsPathRooted(path)
            ? path
            : Path.GetFullPath(Path.Combine(AppRoot, path));
    }

    private static string ResolveAppRoot(string contentRootPath)
    {
        var configuredRoot = Environment.GetEnvironmentVariable("STATS_APP_ROOT");
        if (!string.IsNullOrWhiteSpace(configuredRoot))
        {
            return Path.GetFullPath(configuredRoot);
        }

        var current = new DirectoryInfo(contentRootPath);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "config", "stats.runtime.json")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return Path.GetFullPath(contentRootPath);
    }

    private static string ResolveConfigFile(string? configuredPath, string appRoot, string defaultRelativePath)
    {
        var path = string.IsNullOrWhiteSpace(configuredPath) ? defaultRelativePath : configuredPath;
        var resolvedPath = Path.IsPathRooted(path)
            ? path
            : Path.GetFullPath(Path.Combine(appRoot, path));

        if (!File.Exists(resolvedPath))
        {
            throw new FileNotFoundException($"Required Stats central configuration file was not found: {resolvedPath}", resolvedPath);
        }

        return resolvedPath;
    }

    private static Dictionary<string, string> ReadDefaultMap(JsonElement section)
    {
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var property in section.EnumerateObject())
        {
            var defaultValue = ReadDefault(property.Value);
            if (!string.IsNullOrWhiteSpace(defaultValue))
            {
                values[property.Name] = defaultValue;
            }
        }

        return values;
    }

    private static string? ReadDefault(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object
            && element.TryGetProperty("default", out var defaultElement)
            && defaultElement.ValueKind != JsonValueKind.Null)
        {
            return defaultElement.ToString();
        }

        return element.ValueKind == JsonValueKind.String ? element.GetString() : null;
    }

    private static Dictionary<string, string> ReadLogicalPaths(JsonElement pathsRoot, string appRoot)
    {
        var paths = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["root"] = appRoot,
        };

        foreach (var section in pathsRoot.EnumerateObject())
        {
            if (section.Value.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            foreach (var item in section.Value.EnumerateObject())
            {
                if (item.Value.ValueKind == JsonValueKind.String)
                {
                    paths[$"{section.Name}.{item.Name}"] = item.Value.GetString() ?? string.Empty;
                }
            }
        }

        return paths;
    }

    private Dictionary<string, string?> BuildConfigurationDefaults()
    {
        var defaults = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase)
        {
            ["StatsApi:BaseUrl"] = string.Empty,
            ["StatsWeb:Downstream:FileValidationBaseUrl"] = string.Empty,
            ["StatsWeb:Downstream:FileIngestionBaseUrl"] = string.Empty,
            ["StatsWeb:Downstream:DocumentParsingBaseUrl"] = string.Empty,
            ["StatsWeb:Downstream:TransactionExtractionBaseUrl"] = string.Empty,
            ["StatsWeb:Downstream:DataValidationBaseUrl"] = string.Empty,
            ["StatsWeb:Proxy:IdentityBaseUrl"] = ModuleUrl("IDENTITY_PORT"),
            ["StatsWeb:Proxy:FileValidationBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:FileIngestionBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:DocumentParsingBaseUrl"] = ModuleUrl("DOCUMENT_PARSING_PORT"),
            ["StatsWeb:Proxy:TransactionExtractionBaseUrl"] = ModuleUrl("TRANSACTION_EXTRACTION_PORT"),
            ["StatsWeb:Proxy:DataValidationBaseUrl"] = ModuleUrl("DATA_VALIDATION_PORT"),
        };

        if (LoggingDefaults.TryGetValue("LOG_LEVEL", out var logLevel))
        {
            defaults["Logging:LogLevel:Default"] = logLevel;
        }

        return defaults;
    }

    private static List<string> ReadCsv(string? value)
    {
        return (value ?? string.Empty)
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(origin => !string.Equals(origin, "*", StringComparison.Ordinal))
            .ToList();
    }
}

public sealed class StatsCorrelationMiddleware(RequestDelegate next, ILogger<StatsCorrelationMiddleware> logger)
{
    private const string CorrelationHeader = "X-Correlation-ID";

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = context.Request.Headers.TryGetValue(CorrelationHeader, out var incoming)
            && !string.IsNullOrWhiteSpace(incoming.ToString())
                ? incoming.ToString()
                : Guid.NewGuid().ToString("N");

        context.Response.Headers[CorrelationHeader] = correlationId;
        using var scope = logger.BeginScope(new Dictionary<string, object>
        {
            ["correlation_id"] = correlationId,
            ["service"] = "Stats Web",
            ["module"] = "stats-web",
        });

        await next(context);
    }
}

public static class StatsLoggingBootstrap
{
    public static void Configure(WebApplicationBuilder builder, StatsCentralRuntime centralRuntime)
    {
        var logLevelName = Environment.GetEnvironmentVariable("LOG_LEVEL")
            ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_LEVEL")
            ?? "INFO";
        var logFormat = Environment.GetEnvironmentVariable("LOG_FORMAT")
            ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_FORMAT")
            ?? "json";

        builder.Logging.ClearProviders();
        builder.Logging.SetMinimumLevel(ParseLogLevel(logLevelName));

        if (string.Equals(logFormat, "plain", StringComparison.OrdinalIgnoreCase))
        {
            builder.Logging.AddSimpleConsole(options =>
            {
                options.IncludeScopes = true;
                options.SingleLine = true;
                options.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffK ";
            });
            return;
        }

        builder.Logging.AddJsonConsole(options =>
        {
            options.IncludeScopes = true;
            options.TimestampFormat = "yyyy-MM-ddTHH:mm:ss.fffK";
            options.JsonWriterOptions = new JsonWriterOptions
            {
                Indented = false,
            };
        });
    }

    private static LogLevel ParseLogLevel(string value)
    {
        return value.ToUpperInvariant() switch
        {
            "DEBUG" => LogLevel.Debug,
            "INFO" => LogLevel.Information,
            "WARNING" => LogLevel.Warning,
            "ERROR" => LogLevel.Error,
            "CRITICAL" => LogLevel.Critical,
            _ => LogLevel.Information,
        };
    }
}
// M0 Architecture Hardening End
