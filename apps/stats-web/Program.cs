// M1 - User Access Management Start
// Starts the Module 1 ASP.NET Core web frontend and exposes the Python API base URL to Razor pages.
using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;

var builder = WebApplication.CreateBuilder(args);
var centralRuntime = StatsCentralRuntime.Load(builder.Environment.ContentRootPath);
var loggingOptions = StatsLoggingBootstrap.Configure(builder, centralRuntime);
builder.Configuration.AddInMemoryCollection(centralRuntime.ConfigurationDefaults);

builder.Services.AddRazorPages();
builder.Services.AddHttpClient();
builder.Services.AddSingleton(centralRuntime);
builder.Services.AddSingleton(loggingOptions);
builder.Services.AddScoped<StatsUserContextService>();
if (centralRuntime.CorsAllowedOrigins.Count > 0)
{
    builder.Services.AddCors(options =>
    {
        options.AddPolicy(
            "StatsCorsPolicy",
            policy =>
            {
                policy.WithOrigins(centralRuntime.CorsAllowedOrigins.ToArray())
                    .AllowAnyHeader()
                    .AllowAnyMethod();
            }
        );
    });
}
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
        DataValidationBaseUrl: builder.Configuration["StatsWeb:Proxy:DataValidationBaseUrl"] ?? centralRuntime.ModuleUrl("DATA_VALIDATION_PORT"),
        StatsDataBaseUrl: builder.Configuration["StatsWeb:Proxy:StatsDataBaseUrl"] ?? centralRuntime.ModuleUrl("STATS_DATA_PORT"),
        EmailIngestionBaseUrl: builder.Configuration["StatsWeb:Proxy:EmailIngestionBaseUrl"] ?? centralRuntime.ModuleUrl("EMAIL_INGESTION_PORT")
    )
);
builder.Services.AddSingleton(
    new StatsInternalApiOptions(
        InternalApiKey: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:InternalApiKey", "STATS_INTERNAL_API_KEY")
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
        PowerBiTenantId: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:TenantId", "StatsWeb__PowerBi__TenantId"),
        PowerBiClientId: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:ClientId", "StatsWeb__PowerBi__ClientId"),
        PowerBiClientSecret: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:ClientSecret", "StatsWeb__PowerBi__ClientSecret"),
        PowerBiWorkspaceId: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:WorkspaceId", "StatsWeb__PowerBi__WorkspaceId"),
        PowerBiReportId: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:DashboardReportId", "StatsWeb__PowerBi__DashboardReportId"),
        PowerBiDatasetId: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:DatasetId", "StatsWeb__PowerBi__DatasetId"),
        PowerBiHomeDashboardPageName: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:HomeDashboardPageName", "StatsWeb__PowerBi__HomeDashboardPageName"),
        PowerBiApiBaseUrl: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:PowerBi:ApiBaseUrl", "StatsWeb__PowerBi__ApiBaseUrl", "https://api.powerbi.com/v1.0/myorg"),
        ReportingAsOfDate: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:Reporting:AsOfDate", "STATS_AS_OF_DATE"),
        ReportingDefaultCurrency: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:Reporting:DefaultCurrency", "STATS_REPORTING_DEFAULT_CURRENCY", "NZD"),
        ReportingFxRates: StatsConfigurationValue.Read(builder.Configuration, "StatsWeb:Reporting:FxRates", "STATS_REPORTING_FX_RATES"),
        FabricCapacityName: builder.Configuration["StatsWeb:Fabric:CapacityName"] ?? string.Empty,
        FabricWorkspaceName: builder.Configuration["StatsWeb:Fabric:WorkspaceName"] ?? string.Empty,
        AzureEnvironment: builder.Configuration["StatsWeb:Azure:Environment"] ?? "local",
        KeyVaultUri: builder.Configuration["StatsWeb:Azure:KeyVaultUri"] ?? string.Empty,
        UseManagedIdentity: builder.Configuration.GetValue("StatsWeb:Azure:UseManagedIdentity", false)
    )
);
// M2 End

var app = builder.Build();
app.Logger.LogInformation(
    "Loaded central config. AppRoot={AppRoot}; RuntimeConfig={RuntimeConfig}; PathsConfig={PathsConfig}; LoggingConfig={LoggingConfig}; ModulePorts={ModulePorts}; CorsOrigins={CorsOrigins}.",
    centralRuntime.AppRoot,
    centralRuntime.RuntimeConfigPath,
    centralRuntime.PathsConfigPath,
    centralRuntime.LoggingConfigPath,
    centralRuntime.ModulePorts.Count,
    centralRuntime.CorsAllowedOrigins.Count
);

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseStaticFiles();
app.UseRouting();
if (centralRuntime.CorsAllowedOrigins.Count > 0)
{
    app.UseCors("StatsCorsPolicy");
}
app.UseMiddleware<StatsCorrelationMiddleware>();
// M9 - Stats Data and Persistence Start
// Starts cloud-safe upload processing jobs and lets the browser poll instead of holding a long OCR request open.
app.MapPost(
    "/api/v1/upload-processing-jobs",
    StatsUploadProcessingJobs.StartUploadProcessingJobAsync
);
app.MapGet(
    "/api/v1/upload-processing-jobs/{jobId}",
    StatsUploadProcessingJobs.GetUploadProcessingJobAsync
);
app.MapGet(
    "/api/v1/processing-jobs/{jobId}/steps",
    StatsUploadProcessingJobs.GetUploadProcessingStepsAsync
);
// M9 End
// Returns safe Power BI embed configuration state before the generic module proxy handles API traffic.
app.MapGet(
    "/api/v1/reporting/embed-config",
    StatsReportingEmbedConfig.GetEmbedConfigAsync
);
app.MapGet(
    "/api/v1/reporting/kpis",
    StatsReportingKpis.GetKpisAsync
);
app.MapGet(
    "/api/v1/recognition-settings/active",
    StatsRecognitionSettings.GetActiveAsync
);
app.MapPost(
    "/api/v1/auth/logout",
    (HttpContext context) =>
    {
        if (!StatsSessionCookies.HasValidCsrfHeader(context))
        {
            return Results.StatusCode(StatusCodes.Status403Forbidden);
        }

        StatsSessionCookies.DeleteAccessTokenCookie(context);
        return Results.Ok(new { status = "signed_out" });
    }
);
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

public sealed record StatsCurrentUser(string Email, string Role, bool MustChangePassword, string Id = "")
{
    public bool IsAdmin => string.Equals(Role, "admin", StringComparison.OrdinalIgnoreCase) && !MustChangePassword;
}

public sealed class StatsUserContextService(IHttpClientFactory httpClientFactory, StatsWebProxyOptions proxyOptions)
{
    public const string AccessTokenCookieName = "stats_access_token";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private const string CurrentUserCacheKey = "stats_current_user";

    public async Task<StatsCurrentUser?> GetCurrentUserAsync(HttpContext context)
    {
        // P2-6: resolve identity at most once per request. The proxy, the KPI and
        // embed endpoints, and the page models all call this; without caching each
        // one hits M1 /auth/me again on the same request.
        if (context.Items.TryGetValue(CurrentUserCacheKey, out var cached))
        {
            return cached as StatsCurrentUser;
        }

        var token = AccessToken(context);
        if (string.IsNullOrWhiteSpace(token))
        {
            context.Items[CurrentUserCacheKey] = null;
            return null;
        }

        try
        {
            var client = httpClientFactory.CreateClient();
            using var request = new HttpRequestMessage(HttpMethod.Get, $"{proxyOptions.IdentityBaseUrl.TrimEnd('/')}/api/v1/auth/me");
            request.Headers.TryAddWithoutValidation("Authorization", $"Bearer {token}");
            using var response = await client.SendAsync(request, context.RequestAborted);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            using var stream = await response.Content.ReadAsStreamAsync(context.RequestAborted);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: context.RequestAborted);
            var root = document.RootElement;
            var resolvedUser = new StatsCurrentUser(
                Email: Text(root, "email"),
                Role: Text(root, "role"),
                MustChangePassword: Bool(root, "must_change_password"),
                Id: Text(root, "id")
            );
            context.Items[CurrentUserCacheKey] = resolvedUser;
            return resolvedUser;
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
                or JsonException
        )
        {
            return null;
        }
    }

    public async Task<bool> IsAdminAsync(HttpContext context)
    {
        var user = await GetCurrentUserAsync(context);
        return user?.IsAdmin == true;
    }

    private static string? AccessToken(HttpContext context)
    {
        if (context.Request.Cookies.TryGetValue(AccessTokenCookieName, out var cookieToken)
            && !string.IsNullOrWhiteSpace(cookieToken))
        {
            return cookieToken;
        }

        if (context.Request.Headers.TryGetValue("Authorization", out var authorization)
            && authorization.ToString().StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return authorization.ToString()["Bearer ".Length..].Trim();
        }

        return null;
    }

    private static string Text(JsonElement source, string propertyName)
    {
        return source.TryGetProperty(propertyName, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;
    }

    private static bool Bool(JsonElement source, string propertyName)
    {
        return source.TryGetProperty(propertyName, out var value) && value.ValueKind is JsonValueKind.True or JsonValueKind.False && value.GetBoolean();
    }
}

public sealed record StatsLoggingOptions(
    bool IncludeCorrelationId,
    bool RedactSensitiveValues,
    string Destination
);

// M13 - Containerization Start
public sealed record StatsWebProxyOptions(
    string IdentityBaseUrl,
    string FileValidationBaseUrl,
    string FileIngestionBaseUrl,
    string DocumentParsingBaseUrl,
    string TransactionExtractionBaseUrl,
    string DataValidationBaseUrl,
    string StatsDataBaseUrl,
    string EmailIngestionBaseUrl
);

public sealed record StatsInternalApiOptions(string InternalApiKey);
// M13 End

public static class StatsSessionCookies
{
    public const string CsrfHeaderName = "X-Stats-CSRF";

    public static bool HasValidCsrfHeader(HttpContext context)
    {
        return context.Request.Headers.TryGetValue(CsrfHeaderName, out var csrfHeader)
            && string.Equals(csrfHeader.ToString(), "1", StringComparison.Ordinal);
    }

    public static void SetAccessTokenCookie(HttpContext context, string accessToken)
    {
        context.Response.Cookies.Append(
            StatsUserContextService.AccessTokenCookieName,
            accessToken,
            new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Lax,
                Path = "/"
            }
        );
    }

    public static void DeleteAccessTokenCookie(HttpContext context)
    {
        context.Response.Cookies.Delete(
            StatsUserContextService.AccessTokenCookieName,
            new CookieOptions
            {
                Secure = true,
                SameSite = SameSiteMode.Lax,
                Path = "/"
            }
        );
    }
}
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
    string PowerBiClientId,
    string PowerBiClientSecret,
    string PowerBiWorkspaceId,
    string PowerBiReportId,
    string PowerBiDatasetId,
    string PowerBiHomeDashboardPageName,
    string PowerBiApiBaseUrl,
    string ReportingAsOfDate,
    string ReportingDefaultCurrency,
    string ReportingFxRates,
    string FabricCapacityName,
    string FabricWorkspaceName,
    string AzureEnvironment,
    string KeyVaultUri,
    bool UseManagedIdentity
)
{
    public bool ExternalReportingEmbedConfigured => !string.IsNullOrWhiteSpace(ReportingEmbedConfigUrl);

    public bool DirectPowerBiEmbedConfigured =>
        !string.IsNullOrWhiteSpace(PowerBiTenantId)
        && !string.IsNullOrWhiteSpace(PowerBiClientId)
        && !string.IsNullOrWhiteSpace(PowerBiClientSecret)
        && !string.IsNullOrWhiteSpace(PowerBiWorkspaceId)
        && !string.IsNullOrWhiteSpace(PowerBiReportId);

    // P2-7: KPI executeQueries needs only tenant/client/secret/workspace/dataset,
    // not an embed report id. A KPI-only deployment must not read as not-configured
    // just because no report is set for the (separate) embed path.
    public bool DirectPowerBiKpiConfigured =>
        !string.IsNullOrWhiteSpace(PowerBiTenantId)
        && !string.IsNullOrWhiteSpace(PowerBiClientId)
        && !string.IsNullOrWhiteSpace(PowerBiClientSecret)
        && !string.IsNullOrWhiteSpace(PowerBiWorkspaceId)
        && !string.IsNullOrWhiteSpace(PowerBiDatasetId);

    public bool ReportingEmbedConfigured => ExternalReportingEmbedConfigured || DirectPowerBiEmbedConfigured;
}
// M2 End
// M1 End

public static class StatsConfigurationValue
{
    public static string Read(IConfiguration configuration, string key, string environmentVariable, string fallback = "")
    {
        var configured = configuration[key];
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        var environmentValue = Environment.GetEnvironmentVariable(environmentVariable);
        return string.IsNullOrWhiteSpace(environmentValue) ? fallback : environmentValue;
    }
}

// Queries Power BI semantic-model read data for native Home KPI cards.
public static class StatsReportingKpis
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private const string PowerBiScope = "https://analysis.windows.net/powerbi/api/.default";

    public static async Task<IResult> GetKpisAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebShellOptions shellOptions,
        StatsUserContextService userContext,
        ILoggerFactory loggerFactory
    )
    {
        var selectedCurrency = NormalizeCurrency(context.Request.Query["currency"].ToString());
        var user = await userContext.GetCurrentUserAsync(context);
        if (user is null)
        {
            return Results.Unauthorized();
        }

        if (!user.IsAdmin)
        {
            // L1: return a controlled payload so the browser can explain the state
            // instead of throwing on an empty 403 body.
            return Results.Json(
                new
                {
                    status = "not_authorized",
                    message = "Financial KPI cards are limited to administrators until per-user analytics scoping is enabled.",
                    selected_currency = selectedCurrency,
                    rate_basis = "transaction_date",
                    cards = Array.Empty<object>()
                },
                statusCode: StatusCodes.Status403Forbidden
            );
        }

        var logger = loggerFactory.CreateLogger("StatsReportingKpis");
        try
        {
            var asOfDate = ResolveReportingAsOfDate(shellOptions);
            if (!shellOptions.DirectPowerBiKpiConfigured)
            {
                return Results.Ok(NotConfigured(selectedCurrency, asOfDate));
            }

            var client = httpClientFactory.CreateClient();
            client.Timeout = TimeSpan.FromSeconds(20);
            var accessToken = await GetPowerBiAccessTokenAsync(client, shellOptions, context.RequestAborted);
            var payload = await ExecuteKpiQueryAsync(client, shellOptions, selectedCurrency, asOfDate, accessToken, context.RequestAborted);
            return Results.Ok(ToKpiPayload(payload, selectedCurrency, asOfDate));
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
                or InvalidOperationException
                or JsonException
        )
        {
            logger.LogWarning(exception, "Power BI KPI query could not be completed.");
            return Results.Json(
                new
                {
                    status = "unavailable",
                    message = "Financial KPI cards are temporarily unavailable.",
                    selected_currency = selectedCurrency,
                    rate_basis = "transaction_date",
                    cards = Array.Empty<object>()
                },
                statusCode: StatusCodes.Status502BadGateway
            );
        }
    }

    private static async Task<string> GetPowerBiAccessTokenAsync(
        HttpClient client,
        StatsWebShellOptions shellOptions,
        CancellationToken cancellationToken
    )
    {
        var tokenEndpoint = $"https://login.microsoftonline.com/{WebUtility.UrlEncode(shellOptions.PowerBiTenantId)}/oauth2/v2.0/token";
        using var content = new FormUrlEncodedContent(
        [
            new KeyValuePair<string, string>("grant_type", "client_credentials"),
            new KeyValuePair<string, string>("client_id", shellOptions.PowerBiClientId),
            new KeyValuePair<string, string>("client_secret", shellOptions.PowerBiClientSecret),
            new KeyValuePair<string, string>("scope", PowerBiScope),
        ]);
        using var response = await client.PostAsync(tokenEndpoint, content, cancellationToken);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, cancellationToken);
        return TextAt(payload, "access_token")
            ?? throw new InvalidOperationException("Microsoft identity endpoint did not return an access token.");
    }

    private static async Task<JsonObject> ExecuteKpiQueryAsync(
        HttpClient client,
        StatsWebShellOptions shellOptions,
        string selectedCurrency,
        DateOnly asOfDate,
        string accessToken,
        CancellationToken cancellationToken
    )
    {
        var apiBaseUrl = shellOptions.PowerBiApiBaseUrl.TrimEnd('/');
        var url = $"{apiBaseUrl}/groups/{WebUtility.UrlEncode(shellOptions.PowerBiWorkspaceId)}/datasets/{WebUtility.UrlEncode(shellOptions.PowerBiDatasetId)}/executeQueries";
        var dax = BuildKpiDax(selectedCurrency, asOfDate, shellOptions.ReportingFxRates);
        var payload = new JsonObject
        {
            ["queries"] = new JsonArray(new JsonObject { ["query"] = dax }),
            ["serializerSettings"] = new JsonObject { ["includeNulls"] = true }
        };
        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = JsonContent.Create(payload, options: JsonOptions)
        };
        request.Headers.TryAddWithoutValidation("Authorization", $"Bearer {accessToken}");
        using var response = await client.SendAsync(request, cancellationToken);
        var responseText = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new HttpRequestException($"Power BI executeQueries returned {(int)response.StatusCode}: {responseText}");
        }

        return JsonNode.Parse(responseText)?.AsObject()
            ?? throw new InvalidOperationException("Power BI executeQueries returned an empty response.");
    }

    private static DateOnly ResolveReportingAsOfDate(StatsWebShellOptions shellOptions)
    {
        if (string.IsNullOrWhiteSpace(shellOptions.ReportingAsOfDate))
        {
            return DateOnly.FromDateTime(DateTime.UtcNow);
        }

        if (DateOnly.TryParseExact(
            shellOptions.ReportingAsOfDate.Trim(),
            "yyyy-MM-dd",
            CultureInfo.InvariantCulture,
            DateTimeStyles.None,
            out var configuredDate
        ))
        {
            return configuredDate;
        }

        throw new InvalidOperationException("STATS_AS_OF_DATE must use yyyy-MM-dd format.");
    }

    private static string BuildKpiDax(string selectedCurrency, DateOnly asOfDate, string configuredFxRates)
    {
        var currency = selectedCurrency.Replace("\"", "\"\"", StringComparison.Ordinal);
        var asOfDateLiteral = FormattableString.Invariant($"DATE({asOfDate.Year}, {asOfDate.Month}, {asOfDate.Day})");
        var fxRates = BuildFxRatesDax(configuredFxRates);
        return $$"""
EVALUATE
VAR SelectedCurrency = "{{currency}}"
VAR AsOfDate = {{asOfDateLiteral}}
VAR CurrentMonthStart = DATE(YEAR(AsOfDate), MONTH(AsOfDate), 1)
VAR FxRates = {{fxRates}}
VAR MonthlyBase =
    ADDCOLUMNS(
        SUMMARIZE(
            FILTER('Monthly Expenses', 'Monthly Expenses'[month_start_date] <= CurrentMonthStart),
            'Monthly Expenses'[month_start_date]
        ),
        "converted_expense_total",
            VAR HistoryMonth = 'Monthly Expenses'[month_start_date]
            RETURN COALESCE(
                SUMX(
                    FILTER('Monthly Expenses', 'Monthly Expenses'[month_start_date] = HistoryMonth),
                    VAR SourceCurrency = 'Monthly Expenses'[currency]
                    VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                    RETURN 'Monthly Expenses'[expense_total] * COALESCE(ExchangeRate, 0)
                ),
                0
            ),
        "unconverted_expense_total",
            VAR HistoryMonth = 'Monthly Expenses'[month_start_date]
            RETURN COALESCE(
                SUMX(
                    FILTER('Monthly Expenses', 'Monthly Expenses'[month_start_date] = HistoryMonth),
                    VAR SourceCurrency = 'Monthly Expenses'[currency]
                    VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                    RETURN IF(ISBLANK(ExchangeRate), 'Monthly Expenses'[expense_total], 0)
                ),
                0
            )
    )
VAR LatestReportingMonth =
    MAXX(MonthlyBase, 'Monthly Expenses'[month_start_date])
VAR PreviousReportingMonth =
    MAXX(
        FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] < LatestReportingMonth),
        'Monthly Expenses'[month_start_date]
    )
VAR PriorReportingMonth =
    MAXX(
        FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] < PreviousReportingMonth),
        'Monthly Expenses'[month_start_date]
    )
VAR CurrentMonthExpenses =
    COALESCE(
        MAXX(
            FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] = LatestReportingMonth),
            [converted_expense_total]
        ),
        0
    )
VAR LastMonthExpenses =
    COALESCE(
        MAXX(
            FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] = PreviousReportingMonth),
            [converted_expense_total]
        ),
        0
    )
VAR PreviousMonthExpenses =
    COALESCE(
        MAXX(
            FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] = PriorReportingMonth),
            [converted_expense_total]
        ),
        0
    )
VAR CurrentMonthUnconverted =
    COALESCE(
        MAXX(
            FILTER(MonthlyBase, 'Monthly Expenses'[month_start_date] = LatestReportingMonth),
            [unconverted_expense_total]
        ),
        0
    )
VAR CurrentTopContributor =
    TOPN(
        1,
        ADDCOLUMNS(
            FILTER('Top Expense Contributors', 'Top Expense Contributors'[month_start_date] = LatestReportingMonth),
            "converted_expense_total",
                VAR SourceCurrency = 'Top Expense Contributors'[currency]
                VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                RETURN 'Top Expense Contributors'[expense_total] * COALESCE(ExchangeRate, 0)
        ),
        [converted_expense_total],
        DESC
    )
VAR NotableExpense =
    TOPN(
        1,
        ADDCOLUMNS(
            FILTER('Recent Notable Expenses', 'Recent Notable Expenses'[transaction_date] <= AsOfDate),
            "converted_expense_amount",
                VAR SourceCurrency = 'Recent Notable Expenses'[currency]
                VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                RETURN 'Recent Notable Expenses'[expense_amount] * COALESCE(ExchangeRate, 0)
        ),
        'Recent Notable Expenses'[transaction_date],
        DESC,
        [converted_expense_amount],
        DESC
    )
VAR MonthlyHistoryRows =
    TOPN(
        6,
        MonthlyBase,
        'Monthly Expenses'[month_start_date],
        DESC
    )
VAR LatestCategoryMonth =
    MAXX(
        FILTER(
            'Spending Categories',
            'Spending Categories'[month_start_date] <= CurrentMonthStart
        ),
        'Spending Categories'[month_start_date]
    )
VAR CategoryBase =
    ADDCOLUMNS(
        SUMMARIZE(
            FILTER('Spending Categories', 'Spending Categories'[month_start_date] = LatestCategoryMonth),
            'Spending Categories'[spending_category]
        ),
        "converted_expense_total",
            VAR CategoryName = 'Spending Categories'[spending_category]
            RETURN COALESCE(
                SUMX(
                    FILTER(
                        'Spending Categories',
                        'Spending Categories'[month_start_date] = LatestCategoryMonth
                            && 'Spending Categories'[spending_category] = CategoryName
                    ),
                    VAR SourceCurrency = 'Spending Categories'[currency]
                    VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                    RETURN 'Spending Categories'[expense_total] * COALESCE(ExchangeRate, 0)
                ),
                0
            ),
        "category_transaction_count",
            VAR CategoryName = 'Spending Categories'[spending_category]
            RETURN COALESCE(
                SUMX(
                    FILTER(
                        'Spending Categories',
                        'Spending Categories'[month_start_date] = LatestCategoryMonth
                            && 'Spending Categories'[spending_category] = CategoryName
                    ),
                    'Spending Categories'[transaction_count]
                ),
                0
            ),
        "category_review_required_count",
            VAR CategoryName = 'Spending Categories'[spending_category]
            RETURN COALESCE(
                SUMX(
                    FILTER(
                        'Spending Categories',
                        'Spending Categories'[month_start_date] = LatestCategoryMonth
                            && 'Spending Categories'[spending_category] = CategoryName
                    ),
                    'Spending Categories'[review_required_count]
                ),
                0
            ),
        "converted_uncategorized_expense_total",
            VAR CategoryName = 'Spending Categories'[spending_category]
            RETURN COALESCE(
                SUMX(
                    FILTER(
                        'Spending Categories',
                        'Spending Categories'[month_start_date] = LatestCategoryMonth
                            && 'Spending Categories'[spending_category] = CategoryName
                    ),
                    VAR SourceCurrency = 'Spending Categories'[currency]
                    VAR ExchangeRate = MAXX(FILTER(FxRates, [source_currency] = SourceCurrency && [target_currency] = SelectedCurrency), [rate])
                    RETURN 'Spending Categories'[uncategorized_expense_total] * COALESCE(ExchangeRate, 0)
                ),
                0
            )
    )
VAR CategoryRows =
    TOPN(
        8,
        CategoryBase,
        [converted_expense_total],
        DESC
    )
VAR LatestClassificationMonth =
    MAXX(
        FILTER(
            'Classification Quality',
            'Classification Quality'[month_start_date] <= CurrentMonthStart
        ),
        'Classification Quality'[month_start_date]
    )
VAR ClassificationRows =
    FILTER(
        'Classification Quality',
        'Classification Quality'[month_start_date] = LatestClassificationMonth
    )
RETURN
ROW(
    "last_month_expenses", LastMonthExpenses,
    "this_month_expenses", CurrentMonthExpenses,
    "expense_trend_delta", CurrentMonthExpenses - LastMonthExpenses,
    "this_month_label", FORMAT(LatestReportingMonth, "yyyy-MM"),
    "last_month_label", FORMAT(PreviousReportingMonth, "yyyy-MM"),
    "current_month_unconverted_total", CurrentMonthUnconverted,
    "top_contributor_name", MAXX(CurrentTopContributor, 'Top Expense Contributors'[expense_contributor]),
    "top_contributor_amount", COALESCE(MAXX(CurrentTopContributor, [converted_expense_total]), 0),
    "notable_expense_description", MAXX(NotableExpense, 'Recent Notable Expenses'[description]),
    "notable_expense_amount", COALESCE(MAXX(NotableExpense, [converted_expense_amount]), 0),
    "monthly_history", CONCATENATEX(
        MonthlyHistoryRows,
        FORMAT('Monthly Expenses'[month_start_date], "yyyy-MM") & ":" & FORMAT([converted_expense_total], "0.####"),
        "|",
        'Monthly Expenses'[month_start_date],
        ASC
    ),
    "spending_categories", CONCATENATEX(
        CategoryRows,
        SUBSTITUTE(SUBSTITUTE('Spending Categories'[spending_category], "|", "/"), ":", " ") & ":"
            & FORMAT([converted_expense_total], "0.####") & ":"
            & FORMAT([category_transaction_count], "0") & ":"
            & FORMAT([category_review_required_count], "0") & ":"
            & FORMAT([converted_uncategorized_expense_total], "0.####"),
        "|",
        [converted_expense_total],
        DESC
    ),
    "classification_transaction_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[transaction_count]), 0),
    "classification_classified_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[classified_transaction_count]), 0),
    "classification_unclassified_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[unclassified_transaction_count]), 0),
    "classification_review_required_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[review_required_count]), 0),
    "classification_human_confirmed_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[human_confirmed_count]), 0),
    "classification_low_confidence_ai_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[low_confidence_ai_count]), 0),
    "classification_outside_vocabulary_proposal_count", COALESCE(SUMX(ClassificationRows, 'Classification Quality'[outside_vocabulary_proposal_count]), 0)
)
""";
    }

    private static string BuildFxRatesDax(string configuredFxRates)
    {
        var supportedCurrencies = new[] { "NZD", "PHP", "AUD", "USD" };
        var rates = new Dictionary<(string Source, string Target), decimal>();
        foreach (var currency in supportedCurrencies)
        {
            rates[(currency, currency)] = 1m;
        }

        foreach (var entry in configuredFxRates.Split([',', ';', '|'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var entryParts = entry.Split('=', 2, StringSplitOptions.TrimEntries);
            if (entryParts.Length != 2
                || !decimal.TryParse(entryParts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var rate)
                || rate <= 0)
            {
                continue;
            }

            var currencyParts = entryParts[0].Split(':', 2, StringSplitOptions.TrimEntries);
            if (currencyParts.Length != 2
                || !TryNormalizeCurrency(currencyParts[0], out var sourceCurrency)
                || !TryNormalizeCurrency(currencyParts[1], out var targetCurrency))
            {
                continue;
            }

            rates[(sourceCurrency, targetCurrency)] = rate;
            rates.TryAdd((targetCurrency, sourceCurrency), 1m / rate);
        }

        AddCrossCurrencyRates(rates, supportedCurrencies);

        var rows = rates
            .OrderBy(rate => rate.Key.Source, StringComparer.Ordinal)
            .ThenBy(rate => rate.Key.Target, StringComparer.Ordinal)
            .Select(rate => FormattableString.Invariant(
                $"{{ \"{rate.Key.Source}\", \"{rate.Key.Target}\", {rate.Value.ToString("0.################", CultureInfo.InvariantCulture)} }}"
            ));

        return $"DATATABLE(\"source_currency\", STRING, \"target_currency\", STRING, \"rate\", DOUBLE, {{ {string.Join(", ", rows)} }})";
    }

    private static void AddCrossCurrencyRates(Dictionary<(string Source, string Target), decimal> rates, string[] supportedCurrencies)
    {
        var addedRate = true;
        while (addedRate)
        {
            addedRate = false;
            foreach (var sourceCurrency in supportedCurrencies)
            {
                foreach (var targetCurrency in supportedCurrencies)
                {
                    if (rates.ContainsKey((sourceCurrency, targetCurrency)))
                    {
                        continue;
                    }

                    foreach (var bridgeCurrency in supportedCurrencies)
                    {
                        if (bridgeCurrency == sourceCurrency || bridgeCurrency == targetCurrency)
                        {
                            continue;
                        }

                        if (rates.TryGetValue((sourceCurrency, bridgeCurrency), out var sourceToBridge)
                            && rates.TryGetValue((bridgeCurrency, targetCurrency), out var bridgeToTarget))
                        {
                            rates[(sourceCurrency, targetCurrency)] = sourceToBridge * bridgeToTarget;
                            addedRate = true;
                            break;
                        }
                    }
                }
            }
        }
    }

    private static object ToKpiPayload(JsonObject payload, string selectedCurrency, DateOnly asOfDate)
    {
        var row = payload["results"]?[0]?["tables"]?[0]?["rows"]?[0]?.AsObject()
            ?? throw new InvalidOperationException("Power BI KPI query did not return a result row.");

        var cards = new[]
        {
            Card("last_month_expenses", "Last month expenses", MoneyAt(row, "last_month_expenses"), $"Total debit spending for {TextAt(row, "last_month_label") ?? "the previous calendar month"}."),
            Card("this_month_running", "This month running", MoneyAt(row, "this_month_expenses"), $"Expense total for {TextAt(row, "this_month_label") ?? "the current month"} in the selected currency."),
            Card("top_contributor", "Top contributor", MoneyAt(row, "top_contributor_amount"), TextAt(row, "top_contributor_name") ?? "No contributor for the current month."),
            Card("expense_trend", "Change vs prior month", MoneyAt(row, "expense_trend_delta"), "This month spending minus the previous month; positive means spending is higher."),
            Card("notable_expenses", "Notable expenses", MoneyAt(row, "notable_expense_amount"), TextAt(row, "notable_expense_description") ?? "No recent notable expense.")
        };

        return new
        {
            status = "configured",
            message = "Financial KPIs loaded from the analytics layer.",
            selected_currency = selectedCurrency,
            rate_basis = "transaction_date",
            as_of_date = asOfDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
            this_month_label = TextAt(row, "this_month_label"),
            last_month_label = TextAt(row, "last_month_label"),
            current_month_unconverted_total = MoneyAt(row, "current_month_unconverted_total"),
            has_unconverted_amounts = (MoneyAt(row, "current_month_unconverted_total") ?? 0m) > 0m,
            last_refreshed_at_utc = (string?)null,
            cards,
            monthly_history = ParseMonthlyHistory(TextAt(row, "monthly_history")),
            spending_categories = ParseSpendingCategories(TextAt(row, "spending_categories")),
            classification_quality = new
            {
                transaction_count = WholeNumberAt(row, "classification_transaction_count"),
                classified_transaction_count = WholeNumberAt(row, "classification_classified_count"),
                unclassified_transaction_count = WholeNumberAt(row, "classification_unclassified_count"),
                review_required_count = WholeNumberAt(row, "classification_review_required_count"),
                human_confirmed_count = WholeNumberAt(row, "classification_human_confirmed_count"),
                low_confidence_ai_count = WholeNumberAt(row, "classification_low_confidence_ai_count"),
                outside_vocabulary_proposal_count = WholeNumberAt(row, "classification_outside_vocabulary_proposal_count")
            }
        };
    }

    private static object Card(string id, string title, decimal? amount, string detail)
    {
        return new { id, title, amount, detail };
    }

    private static object[] ParseMonthlyHistory(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return [];
        }

        return value
            .Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(entry =>
            {
                var parts = entry.Split(':', 2, StringSplitOptions.TrimEntries);
                var month = parts.Length > 0 ? parts[0] : string.Empty;
                var amount = parts.Length > 1 && decimal.TryParse(parts[1], NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
                    ? parsed
                    : 0m;
                return new { month, amount };
            })
            .ToArray<object>();
    }

    private static object[] ParseSpendingCategories(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return [];
        }

        return value
            .Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(entry =>
            {
                var parts = entry.Split(':', 5, StringSplitOptions.TrimEntries);
                return new
                {
                    spending_category = parts.Length > 0 ? parts[0] : "uncategorized",
                    expense_total = DecimalPart(parts, 1),
                    transaction_count = WholeNumberPart(parts, 2),
                    review_required_count = WholeNumberPart(parts, 3),
                    uncategorized_expense_total = DecimalPart(parts, 4)
                };
            })
            .ToArray<object>();
    }

    private static object NotConfigured(string selectedCurrency, DateOnly asOfDate)
    {
        return new
        {
            status = "not_configured",
            message = "Financial KPI analytics are not connected yet.",
            selected_currency = selectedCurrency,
            rate_basis = "transaction_date",
            as_of_date = asOfDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture),
            cards = Array.Empty<object>(),
            monthly_history = Array.Empty<object>(),
            spending_categories = Array.Empty<object>(),
            classification_quality = new
            {
                transaction_count = 0,
                classified_transaction_count = 0,
                unclassified_transaction_count = 0,
                review_required_count = 0,
                human_confirmed_count = 0,
                low_confidence_ai_count = 0,
                outside_vocabulary_proposal_count = 0
            }
        };
    }

    private static decimal? MoneyAt(JsonObject payload, string propertyName)
    {
        var value = payload.FirstOrDefault(property => property.Key.EndsWith($"[{propertyName}]", StringComparison.OrdinalIgnoreCase)).Value
            ?? payload[propertyName];
        if (value is null)
        {
            return null;
        }

        if (value is JsonValue jsonValue && jsonValue.TryGetValue<decimal>(out var decimalValue))
        {
            return decimalValue;
        }

        return decimal.TryParse(value.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : null;
    }

    private static long WholeNumberAt(JsonObject payload, string propertyName)
    {
        var value = payload.FirstOrDefault(property => property.Key.EndsWith($"[{propertyName}]", StringComparison.OrdinalIgnoreCase)).Value
            ?? payload[propertyName];
        if (value is null)
        {
            return 0;
        }

        if (value is JsonValue jsonValue && jsonValue.TryGetValue<long>(out var longValue))
        {
            return longValue;
        }

        return decimal.TryParse(value.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
            ? Convert.ToInt64(parsed)
            : 0;
    }

    private static decimal DecimalPart(string[] parts, int index)
    {
        return parts.Length > index && decimal.TryParse(parts[index], NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
            ? parsed
            : 0m;
    }

    private static long WholeNumberPart(string[] parts, int index)
    {
        return parts.Length > index && decimal.TryParse(parts[index], NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed)
            ? Convert.ToInt64(parsed)
            : 0;
    }

    private static string? TextAt(JsonObject? payload, params string[] propertyNames)
    {
        if (payload is null)
        {
            return null;
        }

        foreach (var propertyName in propertyNames)
        {
            if (payload[propertyName]?.GetValue<string>() is { Length: > 0 } exactValue)
            {
                return exactValue;
            }

            var matchingProperty = payload.FirstOrDefault(property => property.Key.EndsWith($"[{propertyName}]", StringComparison.OrdinalIgnoreCase));
            if (matchingProperty.Value?.GetValue<string>() is { Length: > 0 } bracketedValue)
            {
                return bracketedValue;
            }
        }

        return null;
    }

    private static string NormalizeCurrency(string value)
    {
        var normalized = string.IsNullOrWhiteSpace(value) ? "NZD" : value.Trim().ToUpperInvariant();
        return normalized.Length == 3 && normalized.All(char.IsAsciiLetter)
            ? normalized
            : "NZD";
    }

    private static bool TryNormalizeCurrency(string value, out string currency)
    {
        currency = string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim().ToUpperInvariant();
        return currency.Length == 3 && currency.All(char.IsAsciiLetter);
    }
}

// Fetches and sanitizes the reporting embed contract without exposing cloud secrets to the browser.
public static class StatsReportingEmbedConfig
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private const string PowerBiScope = "https://analysis.windows.net/powerbi/api/.default";

    public static async Task<IResult> GetEmbedConfigAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebShellOptions shellOptions,
        StatsUserContextService userContext,
        ILoggerFactory loggerFactory
    )
    {
        var selectedCurrency = NormalizeCurrency(context.Request.Query["currency"].ToString());
        var selectedSurface = NormalizeSurface(context.Request.Query["surface"].ToString());
        var embedUser = await userContext.GetCurrentUserAsync(context);
        if (embedUser is null)
        {
            return Results.Unauthorized();
        }

        // H1: parity with the KPI path. In AppOwnsData mode the View embed token
        // exposes the entire semantic model, so restrict embed configuration to
        // administrators until row-level security scopes analytics per user.
        if (!embedUser.IsAdmin)
        {
            return Results.Json(
                new
                {
                    status = "not_authorized",
                    message = "Financial reporting is limited to administrators until per-user analytics scoping is enabled."
                },
                statusCode: StatusCodes.Status403Forbidden
            );
        }

        if (shellOptions.ExternalReportingEmbedConfigured)
        {
            var externalResult = await GetExternalEmbedConfigAsync(
                context,
                httpClientFactory,
                shellOptions,
                loggerFactory,
                selectedCurrency,
                selectedSurface
            );
            if (!shellOptions.DirectPowerBiEmbedConfigured || !IsNotConfiguredResult(externalResult))
            {
                return externalResult;
            }
        }

        if (shellOptions.DirectPowerBiEmbedConfigured)
        {
            return await GetDirectPowerBiEmbedConfigAsync(
                context,
                httpClientFactory,
                shellOptions,
                loggerFactory,
                selectedCurrency,
                selectedSurface
            );
        }

        return Results.Ok(NotConfigured(selectedCurrency));
    }

    private static async Task<IResult> GetExternalEmbedConfigAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebShellOptions shellOptions,
        ILoggerFactory loggerFactory,
        string selectedCurrency,
        string selectedSurface
    )
    {
        if (string.IsNullOrWhiteSpace(shellOptions.ReportingEmbedConfigUrl))
        {
            return Results.Ok(NotConfigured(selectedCurrency));
        }

        var logger = loggerFactory.CreateLogger("StatsReportingEmbedConfig");
        var targetUrl = BuildTargetUrl(shellOptions.ReportingEmbedConfigUrl, selectedCurrency, selectedSurface);
        using var request = new HttpRequestMessage(HttpMethod.Get, targetUrl);
        if (context.Request.Headers.TryGetValue("Authorization", out var authorizationHeader))
        {
            request.Headers.TryAddWithoutValidation("Authorization", authorizationHeader.ToArray());
        }

        try
        {
            var client = httpClientFactory.CreateClient();
            client.Timeout = TimeSpan.FromSeconds(15);
            using var response = await client.SendAsync(request, context.RequestAborted);
            if (!response.IsSuccessStatusCode)
            {
                logger.LogWarning(
                    "Reporting embed config endpoint returned {StatusCode}.",
                    (int)response.StatusCode
                );
                return Results.Json(
                    new
                    {
                        status = "unavailable",
                        message = "Power BI reporting is temporarily unavailable.",
                        selected_currency = selectedCurrency,
                        rate_basis = "transaction_date"
                    },
                    statusCode: StatusCodes.Status502BadGateway
                );
            }

            var payload = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, context.RequestAborted);
            return Results.Ok(SanitizePayload(payload, selectedCurrency, selectedSurface));
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
                or JsonException
        )
        {
            logger.LogWarning(exception, "Reporting embed config endpoint could not be reached.");
            return Results.Json(
                new
                {
                    status = "unavailable",
                    message = "Power BI reporting is temporarily unavailable.",
                    selected_currency = selectedCurrency,
                    rate_basis = "transaction_date"
                },
                statusCode: StatusCodes.Status502BadGateway
            );
        }
    }

    private static async Task<IResult> GetDirectPowerBiEmbedConfigAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebShellOptions shellOptions,
        ILoggerFactory loggerFactory,
        string selectedCurrency,
        string selectedSurface
    )
    {
        var logger = loggerFactory.CreateLogger("StatsReportingEmbedConfig");
        try
        {
            var client = httpClientFactory.CreateClient();
            client.Timeout = TimeSpan.FromSeconds(20);
            var accessToken = await GetPowerBiAccessTokenAsync(client, shellOptions, context.RequestAborted);
            var report = await GetPowerBiReportAsync(client, shellOptions, accessToken, context.RequestAborted);
            var embedToken = await GeneratePowerBiEmbedTokenAsync(client, shellOptions, report, accessToken, context.RequestAborted);

            var datasetId = TextAt(report, "datasetId") ?? shellOptions.PowerBiDatasetId;
            return Results.Ok(new JsonObject
            {
                ["status"] = "configured",
                ["message"] = "Power BI reporting is connected.",
                ["embed_url"] = TextAt(report, "embedUrl"),
                ["report_id"] = TextAt(report, "id") ?? shellOptions.PowerBiReportId,
                ["dataset_id"] = datasetId,
                ["access_token"] = TextAt(embedToken, "token"),
                ["token_expires_at_utc"] = TextAt(embedToken, "expiration"),
                ["last_refreshed_at_utc"] = null,
                ["selected_currency"] = selectedCurrency,
                ["surface"] = selectedSurface,
                ["rate_basis"] = "transaction_date",
                ["default_page_name"] = DefaultPageNameForSurface(shellOptions, selectedSurface),
                ["pages"] = new JsonArray()
            });
        }
        catch (Exception exception) when (
            exception is HttpRequestException
                or TaskCanceledException
                or OperationCanceledException
                or InvalidOperationException
                or JsonException
        )
        {
            logger.LogWarning(exception, "Power BI embed config could not be generated.");
            return Results.Json(
                new
                {
                    status = "unavailable",
                    message = "Power BI reporting is temporarily unavailable.",
                    selected_currency = selectedCurrency,
                    rate_basis = "transaction_date"
                },
                statusCode: StatusCodes.Status502BadGateway
            );
        }
    }

    private static bool IsNotConfiguredResult(IResult result)
    {
        if (result is not IValueHttpResult valueResult)
        {
            return false;
        }

        var statusProperty = valueResult.Value?.GetType().GetProperty("status");
        return string.Equals(statusProperty?.GetValue(valueResult.Value)?.ToString(), "not_configured", StringComparison.OrdinalIgnoreCase);
    }

    private static async Task<string> GetPowerBiAccessTokenAsync(
        HttpClient client,
        StatsWebShellOptions shellOptions,
        CancellationToken cancellationToken
    )
    {
        var tokenEndpoint = $"https://login.microsoftonline.com/{WebUtility.UrlEncode(shellOptions.PowerBiTenantId)}/oauth2/v2.0/token";
        using var content = new FormUrlEncodedContent(
        [
            new KeyValuePair<string, string>("grant_type", "client_credentials"),
            new KeyValuePair<string, string>("client_id", shellOptions.PowerBiClientId),
            new KeyValuePair<string, string>("client_secret", shellOptions.PowerBiClientSecret),
            new KeyValuePair<string, string>("scope", PowerBiScope),
        ]);
        using var response = await client.PostAsync(tokenEndpoint, content, cancellationToken);
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, cancellationToken);
        return TextAt(payload, "access_token")
            ?? throw new InvalidOperationException("Microsoft identity endpoint did not return an access token.");
    }

    private static async Task<JsonObject> GetPowerBiReportAsync(
        HttpClient client,
        StatsWebShellOptions shellOptions,
        string accessToken,
        CancellationToken cancellationToken
    )
    {
        var apiBaseUrl = shellOptions.PowerBiApiBaseUrl.TrimEnd('/');
        var url = $"{apiBaseUrl}/groups/{WebUtility.UrlEncode(shellOptions.PowerBiWorkspaceId)}/reports/{WebUtility.UrlEncode(shellOptions.PowerBiReportId)}";
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.TryAddWithoutValidation("Authorization", $"Bearer {accessToken}");
        using var response = await client.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, cancellationToken)
            ?? throw new InvalidOperationException("Power BI report lookup returned an empty response.");
    }

    private static async Task<JsonObject> GeneratePowerBiEmbedTokenAsync(
        HttpClient client,
        StatsWebShellOptions shellOptions,
        JsonObject report,
        string accessToken,
        CancellationToken cancellationToken
    )
    {
        var apiBaseUrl = shellOptions.PowerBiApiBaseUrl.TrimEnd('/');
        var url = $"{apiBaseUrl}/groups/{WebUtility.UrlEncode(shellOptions.PowerBiWorkspaceId)}/reports/{WebUtility.UrlEncode(shellOptions.PowerBiReportId)}/GenerateToken";
        var payload = new JsonObject { ["accessLevel"] = "View" };
        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = JsonContent.Create(payload, options: JsonOptions)
        };
        request.Headers.TryAddWithoutValidation("Authorization", $"Bearer {accessToken}");
        using var response = await client.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, cancellationToken)
            ?? throw new InvalidOperationException("Power BI token generation returned an empty response.");
    }

    private static object NotConfigured(string selectedCurrency)
    {
        return new
        {
            status = "not_configured",
            message = "Power BI reporting is not connected yet.",
            selected_currency = selectedCurrency,
            rate_basis = "transaction_date"
        };
    }

    private static JsonObject SanitizePayload(JsonObject? payload, string selectedCurrency, string selectedSurface)
    {
        var result = new JsonObject
        {
            ["status"] = "configured",
            ["message"] = TextAt(payload, "message") ?? "Power BI reporting is connected.",
            ["embed_url"] = TextAt(payload, "embed_url", "embedUrl"),
            ["report_id"] = TextAt(payload, "report_id", "reportId"),
            ["dataset_id"] = TextAt(payload, "dataset_id", "datasetId"),
            ["access_token"] = TextAt(payload, "access_token", "accessToken"),
            ["token_expires_at_utc"] = TextAt(payload, "token_expires_at_utc", "tokenExpiresAtUtc", "expiration"),
            ["last_refreshed_at_utc"] = TextAt(payload, "last_refreshed_at_utc", "lastRefreshedAtUtc"),
            ["selected_currency"] = TextAt(payload, "selected_currency", "selectedCurrency") ?? selectedCurrency,
            ["surface"] = TextAt(payload, "surface") ?? selectedSurface,
            ["rate_basis"] = TextAt(payload, "rate_basis", "rateBasis") ?? "transaction_date",
            ["default_page_name"] = TextAt(payload, "default_page_name", "defaultPageName")
        };

        var pages = payload?["pages"]?.DeepClone();
        if (pages is not null)
        {
            result["pages"] = pages;
        }

        return result;
    }

    private static string BuildTargetUrl(string configuredUrl, string selectedCurrency, string selectedSurface)
    {
        var separator = configuredUrl.Contains('?', StringComparison.Ordinal) ? "&" : "?";
        return $"{configuredUrl}{separator}currency={WebUtility.UrlEncode(selectedCurrency)}&surface={WebUtility.UrlEncode(selectedSurface)}";
    }

    private static string NormalizeCurrency(string value)
    {
        var normalized = string.IsNullOrWhiteSpace(value) ? "NZD" : value.Trim().ToUpperInvariant();
        return normalized.Length == 3 && normalized.All(char.IsAsciiLetter)
            ? normalized
            : "NZD";
    }

    private static string NormalizeSurface(string value)
    {
        return string.Equals(value, "home", StringComparison.OrdinalIgnoreCase) ? "home" : "reports";
    }

    private static string? DefaultPageNameForSurface(StatsWebShellOptions shellOptions, string selectedSurface)
    {
        return selectedSurface == "home" && !string.IsNullOrWhiteSpace(shellOptions.PowerBiHomeDashboardPageName)
            ? shellOptions.PowerBiHomeDashboardPageName
            : null;
    }

    private static string? TextAt(JsonObject? json, params string[] keys)
    {
        if (json is null)
        {
            return null;
        }

        foreach (var key in keys)
        {
            if (json.TryGetPropertyValue(key, out var value) && value is not null)
            {
                return value.GetValueKind() == JsonValueKind.String
                    ? value.GetValue<string>()
                    : value.ToJsonString(JsonOptions);
            }
        }

        return null;
    }
}

// M13 - Containerization Start
// Minimal reverse proxy for browser-originating API calls through the single Stats Web container port.
public static class StatsWebApiProxy
{
    public static async Task ProxyApiRequestAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions,
        StatsUserContextService userContext,
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

        if (IsUnsafeMethod(context.Request.Method)
            && !IsLoginRequest(path, context.Request.Method)
            && !HasCsrfHeader(context))
        {
            context.Response.StatusCode = StatusCodes.Status400BadRequest;
            await context.Response.WriteAsJsonAsync(new { detail = "State-changing API calls require the Stats CSRF header." });
            return;
        }

        var targetUri = new Uri($"{targetBaseUrl.TrimEnd('/')}/api/v1/{path}{context.Request.QueryString}");
        using var requestMessage = new HttpRequestMessage(new HttpMethod(context.Request.Method), targetUri);

        foreach (var header in context.Request.Headers)
        {
            if (IsHopByHopHeader(header.Key)
                || string.Equals(header.Key, "Host", StringComparison.OrdinalIgnoreCase)
                || string.Equals(header.Key, "Cookie", StringComparison.OrdinalIgnoreCase)
                || header.Key.StartsWith("X-Stats-User", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (!requestMessage.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray()))
            {
                requestMessage.Content ??= new StreamContent(context.Request.Body);
                requestMessage.Content.Headers.TryAddWithoutValidation(header.Key, header.Value.ToArray());
            }
        }

        // Trusted identity injection: Stats Web has already authenticated the
        // caller, so inject the resolved user id (any client-supplied copy was
        // stripped above) for downstream M9 user scoping.
        var proxyUser = await userContext.GetCurrentUserAsync(context);
        if (proxyUser is not null && !string.IsNullOrWhiteSpace(proxyUser.Id))
        {
            requestMessage.Headers.TryAddWithoutValidation("X-Stats-User-Id", proxyUser.Id);
            requestMessage.Headers.TryAddWithoutValidation("X-Stats-User-Role", proxyUser.Role);
        }

        if (context.Request.ContentLength > 0 && requestMessage.Content is null)
        {
            requestMessage.Content = new StreamContent(context.Request.Body);
            if (!string.IsNullOrWhiteSpace(context.Request.ContentType))
            {
                requestMessage.Content.Headers.TryAddWithoutValidation("Content-Type", context.Request.ContentType);
            }
        }

        if (!requestMessage.Headers.Contains("Authorization")
            && context.Request.Cookies.TryGetValue(StatsUserContextService.AccessTokenCookieName, out var cookieToken)
            && !string.IsNullOrWhiteSpace(cookieToken))
        {
            requestMessage.Headers.TryAddWithoutValidation("Authorization", $"Bearer {cookieToken}");
        }

        try
        {
            var client = httpClientFactory.CreateClient();
            // M12: scheduled mailbox ingestion and process-imported drive whole
            // documents through parse -> extract -> validate -> save, which can far
            // exceed the 5-minute browser-call default. The Container Apps Job replica
            // timeout (55 min) is the real bound for the scheduled tick, so give those
            // internal long-running routes headroom instead of failing mid-pipeline.
            client.Timeout = IsLongRunningEmailIngestionRequest(path)
                ? TimeSpan.FromMinutes(55)
                : TimeSpan.FromMinutes(5);
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
            var responseBody = await responseMessage.Content.ReadAsByteArrayAsync(context.RequestAborted);
            if (responseMessage.IsSuccessStatusCode && IsTokenIssuingAuthRequest(path, context.Request.Method))
            {
                responseBody = SetCookieAndSanitizeTokenResponse(context, responseBody);
            }

            await context.Response.Body.WriteAsync(responseBody, context.RequestAborted);
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

        if (path.StartsWith("email-ingestions", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("email-ingestion-sources", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.EmailIngestionBaseUrl;
        }

        if (path.StartsWith("transactions/batches", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("transactions/duplicate-checks", StringComparison.OrdinalIgnoreCase)
            || path.Equals("documents", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("documents/", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.StatsDataBaseUrl;
        }

        return string.Empty;
    }

    private static bool IsUnsafeMethod(string method)
    {
        return !HttpMethods.IsGet(method)
            && !HttpMethods.IsHead(method)
            && !HttpMethods.IsOptions(method)
            && !HttpMethods.IsTrace(method);
    }

    private static bool IsLoginRequest(string path, string method)
    {
        return HttpMethods.IsPost(method) && path.Equals("auth/login", StringComparison.OrdinalIgnoreCase);
    }

    // M12: routes that run whole documents through the automated pipeline and can
    // legitimately take much longer than a browser API call.
    private static bool IsLongRunningEmailIngestionRequest(string path)
    {
        return path.StartsWith("email-ingestions/scheduled-runs", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("email-ingestions/process-imported", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("email-ingestions/automated-runs", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsTokenIssuingAuthRequest(string path, string method)
    {
        return HttpMethods.IsPost(method)
            && (path.Equals("auth/login", StringComparison.OrdinalIgnoreCase)
                || path.Equals("auth/refresh", StringComparison.OrdinalIgnoreCase));
    }

    private static bool HasCsrfHeader(HttpContext context)
    {
        return context.Request.Headers.TryGetValue(StatsSessionCookies.CsrfHeaderName, out var value)
            && string.Equals(value.ToString(), "1", StringComparison.Ordinal);
    }

    private static byte[] SetCookieAndSanitizeTokenResponse(HttpContext context, byte[] responseBody)
    {
        try
        {
            var payload = JsonNode.Parse(responseBody)?.AsObject();
            var accessToken = payload?["access_token"]?.GetValue<string>();
            if (string.IsNullOrWhiteSpace(accessToken))
            {
                return responseBody;
            }

            StatsSessionCookies.SetAccessTokenCookie(context, accessToken);
            payload!.Remove("access_token");
            payload["session"] = "cookie";
            return JsonSerializer.SerializeToUtf8Bytes(payload, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        }
        catch (Exception exception) when (
            exception is JsonException
                or InvalidOperationException
                or FormatException
        )
        {
            return responseBody;
        }
    }

    private static bool IsHopByHopHeader(string headerName)
    {
        return string.Equals(headerName, "Connection", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Keep-Alive", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Proxy-Authenticate", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Proxy-Authorization", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Content-Length", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "TE", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Trailer", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Transfer-Encoding", StringComparison.OrdinalIgnoreCase)
            || string.Equals(headerName, "Upgrade", StringComparison.OrdinalIgnoreCase);
    }
}

public static class StatsRecognitionSettings
{
    public static async Task<IResult> GetActiveAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions,
        StatsInternalApiOptions internalApiOptions,
        StatsUserContextService userContext
    )
    {
        if (await userContext.GetCurrentUserAsync(context) is null)
        {
            return Results.Unauthorized();
        }

        if (string.IsNullOrWhiteSpace(proxyOptions.StatsDataBaseUrl))
        {
            return Results.Problem("Stats Data recognition settings are not configured.", statusCode: StatusCodes.Status503ServiceUnavailable);
        }

        var client = httpClientFactory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/active"
        );
        if (!string.IsNullOrWhiteSpace(internalApiOptions.InternalApiKey))
        {
            request.Headers.TryAddWithoutValidation("X-Stats-Internal-Key", internalApiOptions.InternalApiKey);
        }

        using var response = await client.SendAsync(request, context.RequestAborted);
        var content = await response.Content.ReadAsStringAsync(context.RequestAborted);
        return Results.Content(
            content,
            response.Content.Headers.ContentType?.ToString() ?? "application/json",
            statusCode: (int)response.StatusCode
        );
    }
}

// M9 - Stats Data and Persistence Start
public static class StatsUploadProcessingJobs
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static async Task<IResult> StartUploadProcessingJobAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions,
        StatsInternalApiOptions internalApiOptions,
        ILoggerFactory loggerFactory
    )
    {
        var uploadStartedAt = DateTimeOffset.UtcNow;
        var uploadStopwatch = Stopwatch.StartNew();
        var logger = loggerFactory.CreateLogger("StatsUploadProcessingJobs");
        var form = await context.Request.ReadFormAsync(context.RequestAborted);
        var file = form.Files.GetFile("file");
        if (file is null || file.Length == 0)
        {
            return Results.BadRequest(new { detail = "A document file is required." });
        }

        var metadata = new UploadProcessingMetadata(
            IngestionId: FormValue(form, "ingestion_id"),
            UploadedByUserId: FormValue(form, "uploaded_by_user_id"),
            OriginalFilename: file.FileName,
            SourceType: FormValue(form, "source_type") ?? "manual_upload",
            SourceId: FormValue(form, "source_id") ?? "stats-web-upload",
            Sha256: FormValue(form, "sha256"),
            DetectedMimeType: FormValue(form, "detected_mime_type") ?? file.ContentType,
            ContentType: file.ContentType,
            AllowOcrFallback: FormValue(form, "allow_ocr_fallback") ?? "true",
            PageLimit: FormValue(form, "page_limit"),
            ClassificationThreshold: FormValue(form, "classification_threshold") ?? "0.1"
        );

        var tempPath = Path.Combine(Path.GetTempPath(), $"stats-upload-{Guid.NewGuid():N}-{Path.GetFileName(file.FileName)}");
        await using (var target = File.Create(tempPath))
        {
            await file.CopyToAsync(target, context.RequestAborted);
        }

        var client = LongRunningClient(httpClientFactory);
        var jobResponse = await client.PostAsJsonAsync(
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/processing-jobs",
            new
            {
                ingestion_id = metadata.IngestionId,
                uploaded_by_user_id = metadata.UploadedByUserId,
                original_filename = metadata.OriginalFilename,
                source_type = metadata.SourceType,
                source_id = metadata.SourceId,
                sha256 = metadata.Sha256,
                message = "Document uploaded. Stats is preparing to read it."
            },
            JsonOptions,
            context.RequestAborted
        );

        if (!jobResponse.IsSuccessStatusCode)
        {
            TryDeleteTempFile(tempPath);
            return Results.StatusCode(StatusCodes.Status502BadGateway);
        }

        var job = await jobResponse.Content.ReadFromJsonAsync<JsonObject>(JsonOptions, context.RequestAborted);
        var jobId = job?["job_id"]?.GetValue<string>();
        if (string.IsNullOrWhiteSpace(jobId))
        {
            TryDeleteTempFile(tempPath);
            return Results.StatusCode(StatusCodes.Status502BadGateway);
        }

        uploadStopwatch.Stop();
        try
        {
            await AppendProcessingStepAsync(
                client,
                proxyOptions,
                jobId,
                "StatsWeb",
                "document_upload",
                "completed",
                uploadStartedAt,
                DateTimeOffset.UtcNow,
                uploadStopwatch.ElapsedMilliseconds,
                new JsonObject
                {
                    ["filename"] = metadata.OriginalFilename,
                    ["content_type"] = metadata.ContentType,
                    ["detected_mime_type"] = metadata.DetectedMimeType,
                    ["size_bytes"] = file.Length,
                    ["ingestion_id"] = metadata.IngestionId,
                    ["source_type"] = metadata.SourceType
                }
            );
        }
        catch (Exception ex)
        {
            TryDeleteTempFile(tempPath);
            logger.LogError(ex, "Failed to record initial upload processing step. job_id={JobId}", jobId);
            try
            {
                await UpdateJobAsync(
                    client,
                    proxyOptions,
                    jobId,
                    "failed",
                    "document_upload",
                    "Document upload could not be tracked.",
                    errorDetail: "Failed to record initial upload processing step."
                );
            }
            catch (Exception updateEx)
            {
                logger.LogWarning(updateEx, "Failed to mark upload processing job failed after upload-step write failure. job_id={JobId}", jobId);
            }
            return Results.StatusCode(StatusCodes.Status502BadGateway);
        }
        logger.LogInformation(
            "Document processing step completed. job_id={JobId} module={ModuleName} step={StepName} status={Status} duration_ms={DurationMs}",
            jobId,
            "StatsWeb",
            "document_upload",
            "completed",
            uploadStopwatch.ElapsedMilliseconds
        );

        _ = Task.Run(
            () => RunProcessingJobAsync(jobId, tempPath, metadata, proxyOptions, internalApiOptions, httpClientFactory, loggerFactory),
            CancellationToken.None
        );

        return Results.Accepted($"/api/v1/upload-processing-jobs/{jobId}", job);
    }

    public static async Task<IResult> GetUploadProcessingJobAsync(
        string jobId,
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions
    )
    {
        var client = LongRunningClient(httpClientFactory);
        using var response = await client.GetAsync(
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/processing-jobs/{WebUtility.UrlEncode(jobId)}",
            context.RequestAborted
        );
        var payload = await response.Content.ReadAsStringAsync(context.RequestAborted);
        return Results.Content(payload, "application/json", statusCode: (int)response.StatusCode);
    }

    public static async Task<IResult> GetUploadProcessingStepsAsync(
        string jobId,
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions
    )
    {
        var client = LongRunningClient(httpClientFactory);
        using var response = await client.GetAsync(
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/processing-jobs/{WebUtility.UrlEncode(jobId)}/steps",
            context.RequestAborted
        );
        var payload = await response.Content.ReadAsStringAsync(context.RequestAborted);
        return Results.Content(payload, "application/json", statusCode: (int)response.StatusCode);
    }

    private static async Task RunProcessingJobAsync(
        string jobId,
        string tempPath,
        UploadProcessingMetadata metadata,
        StatsWebProxyOptions proxyOptions,
        StatsInternalApiOptions internalApiOptions,
        IHttpClientFactory httpClientFactory,
        ILoggerFactory loggerFactory
    )
    {
        var logger = loggerFactory.CreateLogger("StatsUploadProcessingJobs");
        var client = LongRunningClient(httpClientFactory);
        try
        {
            await UpdateJobAsync(client, proxyOptions, jobId, "running", "parsing", "Stats is reading the document text.");
            var parseResult = await RunTimedStepAsync(
                client,
                proxyOptions,
                logger,
                jobId,
                "M5",
                "document_parsing",
                () => ParseDocumentAsync(client, proxyOptions, tempPath, metadata),
                result => ParseStepMetadata(result, metadata)
            );
            var parseId = TextAt(parseResult, "parse_id");

            if (TextAt(parseResult, "status") == "failed")
            {
                await UpdateJobAsync(
                    client,
                    proxyOptions,
                    jobId,
                    "failed",
                    "failed",
                    "Document parsing needs review before Stats can continue.",
                    parseId: parseId,
                    errorDetail: "Document parsing returned failed status."
                );
                return;
            }

            await UpdateJobAsync(client, proxyOptions, jobId, "running", "extracting", "Text was read. Stats is finding transaction details.", parseId: parseId);
            var extractionResult = await RunTimedStepAsync(
                client,
                proxyOptions,
                logger,
                jobId,
                "M7",
                "transaction_extraction",
                () => PostJsonAsync(
                    client,
                    $"{proxyOptions.TransactionExtractionBaseUrl.TrimEnd('/')}/api/v1/extractions",
                    BuildExtractionRequest(parseResult)
                ),
                ExtractionStepMetadata
            );
            var extractionId = TextAt(extractionResult, "extraction_id");

            await UpdateJobAsync(
                client,
                proxyOptions,
                jobId,
                "running",
                "validating",
                "Transactions were found. Stats is checking the details.",
                parseId: parseId,
                extractionId: extractionId
            );
            var validationResult = await RunTimedStepAsync(
                client,
                proxyOptions,
                logger,
                jobId,
                "M8",
                "data_validation",
                () => PostJsonAsync(
                    client,
                    $"{proxyOptions.DataValidationBaseUrl.TrimEnd('/')}/api/v1/validations",
                    BuildValidationRequest(extractionResult, FetchActiveRecognitionContextAsync(client, proxyOptions, internalApiOptions))
                ),
                ValidationStepMetadata
            );

            await UpdateJobAsync(
                client,
                proxyOptions,
                jobId,
                "completed",
                "completed",
                "Transactions checked. Review the results before saving.",
                parseId: parseId,
                extractionId: extractionId,
                validationId: TextAt(validationResult, "validation_id"),
                resultPayload: new JsonObject
                {
                    ["parse_result"] = parseResult.DeepClone(),
                    ["extraction_result"] = extractionResult.DeepClone(),
                    ["validation_result"] = validationResult.DeepClone()
                }
            );
        }
        catch (Exception exception)
        {
            logger.LogWarning(exception, "Upload processing job {JobId} failed.", jobId);
            try
            {
                await UpdateJobAsync(
                    client,
                    proxyOptions,
                    jobId,
                    "failed",
                    "failed",
                    "Document processing failed. Choose another file or try again.",
                    errorDetail: SafeErrorMessage(exception.Message)
                );
            }
            catch (Exception updateException)
            {
                logger.LogError(updateException, "Upload processing job {JobId} failed and the failure status could not be persisted.", jobId);
            }
        }
        finally
        {
            TryDeleteTempFile(tempPath);
        }
    }

    private static async Task<JsonObject> ParseDocumentAsync(
        HttpClient client,
        StatsWebProxyOptions proxyOptions,
        string tempPath,
        UploadProcessingMetadata metadata
    )
    {
        await using var stream = File.OpenRead(tempPath);
        using var form = new MultipartFormDataContent();
        var fileContent = new StreamContent(stream);
        if (!string.IsNullOrWhiteSpace(metadata.ContentType))
        {
            fileContent.Headers.TryAddWithoutValidation("Content-Type", metadata.ContentType);
        }
        form.Add(fileContent, "file", metadata.OriginalFilename);
        AddForm(form, "ingestion_id", metadata.IngestionId);
        AddForm(form, "source_type", metadata.SourceType);
        AddForm(form, "source_id", metadata.SourceId);
        AddForm(form, "sha256", metadata.Sha256);
        AddForm(form, "allow_ocr_fallback", metadata.AllowOcrFallback);
        if (!string.IsNullOrWhiteSpace(metadata.PageLimit))
        {
            AddForm(form, "page_limit", metadata.PageLimit);
        }
        AddForm(form, "classification_threshold", metadata.ClassificationThreshold);

        return await PostMultipartAsync(
            client,
            $"{proxyOptions.DocumentParsingBaseUrl.TrimEnd('/')}/api/v1/parses",
            form
        );
    }

    private static JsonObject BuildExtractionRequest(JsonObject parseResult)
    {
        var documentInfo = parseResult["document"] as JsonObject ?? new JsonObject();
        var classification = parseResult["classification"] as JsonObject ?? new JsonObject();
        return new JsonObject
        {
            ["parse_id"] = parseResult["parse_id"]?.DeepClone(),
            ["document"] = new JsonObject
            {
                ["original_filename"] = documentInfo["original_filename"]?.DeepClone(),
                ["normalized_filename"] = documentInfo["normalized_filename"]?.DeepClone(),
                ["ingestion_id"] = documentInfo["ingestion_id"]?.DeepClone(),
                ["source_type"] = documentInfo["source_type"]?.DeepClone(),
                ["source_id"] = documentInfo["source_id"]?.DeepClone(),
                ["sha256"] = documentInfo["sha256"]?.DeepClone()
            },
            ["document_type"] = classification["document_type"]?.DeepClone() ?? documentInfo["document_type"]?.DeepClone() ?? "unknown",
            ["classification_confidence"] = classification["confidence"]?.DeepClone(),
            ["classification"] = classification.DeepClone(),
            ["text"] = parseResult["text"]?.DeepClone() ?? "",
            ["pages"] = parseResult["pages"]?.DeepClone() ?? new JsonArray(),
            ["metadata"] = parseResult["metadata"]?.DeepClone() ?? new JsonObject(),
            ["quality"] = parseResult["quality"]?.DeepClone(),
            ["findings"] = parseResult["findings"]?.DeepClone() ?? new JsonArray()
        };
    }

    private static JsonObject BuildValidationRequest(JsonObject extractionResult, JsonObject activeRecognitionContext)
    {
        var classification = extractionResult["classification"] as JsonObject ?? new JsonObject();
        return new JsonObject
        {
            ["extraction_id"] = extractionResult["extraction_id"]?.DeepClone(),
            ["parse_id"] = extractionResult["parse_id"]?.DeepClone(),
            ["document"] = extractionResult["document"]?.DeepClone(),
            ["document_type"] = extractionResult["document_type"]?.DeepClone(),
            ["document_type_confidence"] = classification["confidence"]?.DeepClone(),
            ["document_type_status"] = classification["status"]?.DeepClone(),
            ["document_type_reason_codes"] = classification["reason_codes"]?.DeepClone() ?? new JsonArray(),
            ["document_recognition_suggestion_id"] = classification["recognition_suggestion_id"]?.DeepClone(),
            ["document_recognition_suggestion_status"] = classification["recognition_suggestion_status"]?.DeepClone() ?? "none",
            ["suggested_document_type"] = classification["suggested_document_type"]?.DeepClone(),
            ["suggested_document_subtype"] = classification["suggested_document_subtype"]?.DeepClone(),
            ["document_suggestion_confidence"] = classification["suggestion_confidence"]?.DeepClone(),
            ["document_suggestion_reason_codes"] = classification["suggestion_reason_codes"]?.DeepClone() ?? new JsonArray(),
            ["document_suggestion_source"] = classification["suggestion_source"]?.DeepClone(),
            ["document_suggestion_evidence_ref"] = classification["suggestion_evidence_ref"]?.DeepClone(),
            ["transaction_candidates"] = extractionResult["transaction_candidates"]?.DeepClone() ?? new JsonArray(),
            ["financial_field_candidates"] = extractionResult["financial_field_candidates"]?.DeepClone() ?? new JsonArray(),
            ["section_candidates"] = extractionResult["section_candidates"]?.DeepClone() ?? new JsonArray(),
            ["entity_candidates"] = extractionResult["entity_candidates"]?.DeepClone() ?? new JsonArray(),
            ["reference_candidates"] = extractionResult["reference_candidates"]?.DeepClone() ?? new JsonArray(),
            ["line_item_candidates"] = extractionResult["line_item_candidates"]?.DeepClone() ?? new JsonArray(),
            ["installment_candidates"] = extractionResult["installment_candidates"]?.DeepClone() ?? new JsonArray(),
            ["reconciliation"] = extractionResult["reconciliation"]?.DeepClone(),
            ["active_recognition_context"] = activeRecognitionContext.DeepClone(),
            ["findings"] = extractionResult["findings"]?.DeepClone() ?? new JsonArray()
        };
    }

    private static JsonObject FetchActiveRecognitionContextAsync(
        HttpClient client,
        StatsWebProxyOptions proxyOptions,
        StatsInternalApiOptions internalApiOptions
    )
    {
        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Get,
                $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/active"
            );
            if (!string.IsNullOrWhiteSpace(internalApiOptions.InternalApiKey))
            {
                request.Headers.TryAddWithoutValidation("X-Stats-Internal-Key", internalApiOptions.InternalApiKey);
            }
            using var response = client.Send(request);
            if (!response.IsSuccessStatusCode)
            {
                return new JsonObject();
            }
            using var stream = response.Content.ReadAsStream();
            var payload = JsonNode.Parse(stream) as JsonObject;
            return payload?["recognition_context"]?.DeepClone() as JsonObject ?? new JsonObject();
        }
        catch
        {
            return new JsonObject();
        }
    }

    private static async Task UpdateJobAsync(
        HttpClient client,
        StatsWebProxyOptions proxyOptions,
        string jobId,
        string status,
        string stage,
        string message,
        string? parseId = null,
        string? extractionId = null,
        string? validationId = null,
        JsonObject? resultPayload = null,
        string? errorDetail = null
    )
    {
        using var response = await client.PatchAsJsonAsync(
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/processing-jobs/{WebUtility.UrlEncode(jobId)}",
            new
            {
                status,
                stage,
                message,
                parse_id = parseId,
                extraction_id = extractionId,
                validation_id = validationId,
                result_payload = resultPayload,
                error_detail = errorDetail
            },
            JsonOptions
        );
        response.EnsureSuccessStatusCode();
    }

    private static async Task<JsonObject> RunTimedStepAsync(
        HttpClient client,
        StatsWebProxyOptions proxyOptions,
        ILogger logger,
        string jobId,
        string moduleName,
        string stepName,
        Func<Task<JsonObject>> action,
        Func<JsonObject, JsonObject> metadataFactory
    )
    {
        var startedAt = DateTimeOffset.UtcNow;
        var stopwatch = Stopwatch.StartNew();
        try
        {
            var result = await action();
            stopwatch.Stop();
            var status = TextAt(result, "status") ?? "completed";
            var normalizedStatus = status == "completed" ? "completed" : status;
            var metadata = metadataFactory(result);
            await AppendProcessingStepAsync(
                client,
                proxyOptions,
                jobId,
                moduleName,
                stepName,
                normalizedStatus,
                startedAt,
                DateTimeOffset.UtcNow,
                stopwatch.ElapsedMilliseconds,
                metadata
            );
            logger.LogInformation(
                "Document processing step completed. job_id={JobId} module={ModuleName} step={StepName} status={Status} duration_ms={DurationMs}",
                jobId,
                moduleName,
                stepName,
                normalizedStatus,
                stopwatch.ElapsedMilliseconds
            );
            return result;
        }
        catch (Exception exception)
        {
            stopwatch.Stop();
            await AppendProcessingStepAsync(
                client,
                proxyOptions,
                jobId,
                moduleName,
                stepName,
                "failed",
                startedAt,
                DateTimeOffset.UtcNow,
                stopwatch.ElapsedMilliseconds,
                new JsonObject(),
                errorCode: exception.GetType().Name,
                errorMessage: SafeErrorMessage(exception.Message)
            );
            logger.LogWarning(
                exception,
                "Document processing step failed. job_id={JobId} module={ModuleName} step={StepName} duration_ms={DurationMs}",
                jobId,
                moduleName,
                stepName,
                stopwatch.ElapsedMilliseconds
            );
            throw;
        }
    }

    private static async Task AppendProcessingStepAsync(
        HttpClient client,
        StatsWebProxyOptions proxyOptions,
        string jobId,
        string moduleName,
        string stepName,
        string status,
        DateTimeOffset startedAt,
        DateTimeOffset completedAt,
        long durationMs,
        JsonObject metadata,
        string? errorCode = null,
        string? errorMessage = null
    )
    {
        using var response = await client.PostAsJsonAsync(
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/processing-jobs/{WebUtility.UrlEncode(jobId)}/steps",
            new
            {
                module_name = moduleName,
                step_name = stepName,
                status,
                started_at_utc = startedAt.UtcDateTime.ToString("O"),
                completed_at_utc = completedAt.UtcDateTime.ToString("O"),
                duration_ms = durationMs,
                metadata,
                error_code = errorCode,
                error_message = errorMessage
            },
            JsonOptions
        );
        response.EnsureSuccessStatusCode();
    }

    private static JsonObject ParseStepMetadata(JsonObject result, UploadProcessingMetadata uploadMetadata)
    {
        var metadata = result["metadata"] as JsonObject ?? new JsonObject();
        var strategy = result["strategy"] as JsonObject ?? new JsonObject();
        var classification = result["classification"] as JsonObject ?? new JsonObject();
        var pages = result["pages"] as JsonArray ?? new JsonArray();
        var findings = result["findings"] as JsonArray ?? new JsonArray();
        return new JsonObject
        {
            ["parse_id"] = result["parse_id"]?.DeepClone(),
            ["filename"] = uploadMetadata.OriginalFilename,
            ["status"] = result["status"]?.DeepClone(),
            ["document_type"] = classification["document_type"]?.DeepClone(),
            ["document_subtype"] = classification["document_subtype"]?.DeepClone(),
            ["strategy"] = strategy["strategy"]?.DeepClone() ?? result["strategy"]?.DeepClone(),
            ["extraction_method"] = metadata["extraction_method"]?.DeepClone(),
            ["ocr_engine"] = metadata["ocr_engine"]?.DeepClone(),
            ["ocr_attempted"] = metadata["ocr_attempted"]?.DeepClone(),
            ["page_count"] = metadata["page_count"]?.DeepClone(),
            ["pages_processed"] = metadata["pages_processed"]?.DeepClone(),
            ["page_result_count"] = pages.Count,
            ["finding_count"] = findings.Count
        };
    }

    private static JsonObject ExtractionStepMetadata(JsonObject result)
    {
        var summary = result["summary"] as JsonObject ?? new JsonObject();
        var reconciliation = result["reconciliation"] as JsonObject ?? new JsonObject();
        var findings = result["findings"] as JsonArray ?? new JsonArray();
        return new JsonObject
        {
            ["extraction_id"] = result["extraction_id"]?.DeepClone(),
            ["parse_id"] = result["parse_id"]?.DeepClone(),
            ["status"] = result["status"]?.DeepClone(),
            ["transaction_candidate_count"] = summary["transaction_candidate_count"]?.DeepClone(),
            ["financial_field_candidate_count"] = summary["financial_field_candidate_count"]?.DeepClone(),
            ["section_candidate_count"] = summary["section_candidate_count"]?.DeepClone(),
            ["line_item_count"] = summary["line_item_count"]?.DeepClone(),
            ["installment_count"] = summary["installment_count"]?.DeepClone(),
            ["reconciliation_status"] = reconciliation["status"]?.DeepClone(),
            ["finding_count"] = findings.Count
        };
    }

    private static JsonObject ValidationStepMetadata(JsonObject result)
    {
        var summary = result["summary"] as JsonObject ?? new JsonObject();
        var findings = result["findings"] as JsonArray ?? new JsonArray();
        return new JsonObject
        {
            ["validation_id"] = result["validation_id"]?.DeepClone(),
            ["extraction_id"] = result["extraction_id"]?.DeepClone(),
            ["parse_id"] = result["parse_id"]?.DeepClone(),
            ["status"] = result["status"]?.DeepClone(),
            ["normalized_record_count"] = summary["normalized_record_count"]?.DeepClone(),
            ["review_item_count"] = summary["review_item_count"]?.DeepClone(),
            ["document_review_status"] = summary["document_review_status"]?.DeepClone(),
            ["recommended_action"] = summary["recommended_action"]?.DeepClone(),
            ["finding_count"] = findings.Count
        };
    }

    private static string SafeErrorMessage(string message)
    {
        return string.IsNullOrWhiteSpace(message)
            ? "Step failed."
            : message.Length <= 1000 ? message : message[..1000];
    }

    private static async Task<JsonObject> PostJsonAsync(HttpClient client, string url, JsonObject payload)
    {
        using var response = await client.PostAsJsonAsync(url, payload, JsonOptions);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return result ?? throw new InvalidOperationException("Stats module returned an empty response.");
    }

    private static async Task<JsonObject> PostMultipartAsync(HttpClient client, string url, MultipartFormDataContent form)
    {
        using var response = await client.PostAsync(url, form);
        response.EnsureSuccessStatusCode();
        var result = await response.Content.ReadFromJsonAsync<JsonObject>(JsonOptions);
        return result ?? throw new InvalidOperationException("Stats module returned an empty response.");
    }

    private static HttpClient LongRunningClient(IHttpClientFactory httpClientFactory)
    {
        var client = httpClientFactory.CreateClient();
        client.Timeout = TimeSpan.FromMinutes(30);
        return client;
    }

    private static void AddForm(MultipartFormDataContent form, string name, string? value)
    {
        form.Add(new StringContent(value ?? string.Empty), name);
    }

    private static string? FormValue(IFormCollection form, string key)
    {
        return form.TryGetValue(key, out var value) ? Convert.ToString(value) : null;
    }

    private static string? TextAt(JsonObject json, string key)
    {
        return json.TryGetPropertyValue(key, out var value) ? value?.GetValue<string>() : null;
    }

    private static void TryDeleteTempFile(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch
        {
            // Best-effort cleanup only.
        }
    }
}

public sealed record UploadProcessingMetadata(
    string? IngestionId,
    string? UploadedByUserId,
    string OriginalFilename,
    string SourceType,
    string SourceId,
    string? Sha256,
    string? DetectedMimeType,
    string? ContentType,
    string AllowOcrFallback,
    string? PageLimit,
    string ClassificationThreshold
);
// M9 End
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

        using var runtimeDocument = ParseConfigDocument(runtimeConfigPath, "runtime");
        using var pathsDocument = ParseConfigDocument(pathsConfigPath, "paths");
        using var loggingDocument = ParseConfigDocument(loggingConfigPath, "logging");

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
        runtime.ValidateRequiredProxyPorts();
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

    public void ValidateRequiredProxyPorts()
    {
        foreach (var portKey in new[]
        {
            "IDENTITY_PORT",
            "FILE_VALIDATION_PORT",
            "DOCUMENT_PARSING_PORT",
            "TRANSACTION_EXTRACTION_PORT",
            "DATA_VALIDATION_PORT",
            "STATS_DATA_PORT",
            "EMAIL_INGESTION_PORT",
        })
        {
            _ = ModuleUrl(portKey);
        }
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

    private static JsonDocument ParseConfigDocument(string path, string configName)
    {
        try
        {
            return JsonDocument.Parse(File.ReadAllText(path));
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException(
                $"Stats Web could not parse the central {configName} configuration file at {path}. Fix the JSON syntax before startup.",
                exception
            );
        }
        catch (IOException exception)
        {
            throw new InvalidOperationException(
                $"Stats Web could not read the central {configName} configuration file at {path}.",
                exception
            );
        }
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
            ["StatsWeb:Downstream:EmailIngestionBaseUrl"] = string.Empty,
            ["StatsWeb:Proxy:IdentityBaseUrl"] = ModuleUrl("IDENTITY_PORT"),
            ["StatsWeb:Proxy:FileValidationBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:FileIngestionBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:DocumentParsingBaseUrl"] = ModuleUrl("DOCUMENT_PARSING_PORT"),
            ["StatsWeb:Proxy:TransactionExtractionBaseUrl"] = ModuleUrl("TRANSACTION_EXTRACTION_PORT"),
            ["StatsWeb:Proxy:DataValidationBaseUrl"] = ModuleUrl("DATA_VALIDATION_PORT"),
            ["StatsWeb:Proxy:StatsDataBaseUrl"] = ModuleUrl("STATS_DATA_PORT"),
            ["StatsWeb:Proxy:EmailIngestionBaseUrl"] = ModuleUrl("EMAIL_INGESTION_PORT"),
        };

        if (LoggingDefaults.TryGetValue("LOG_LEVEL", out var logLevel))
        {
            defaults["Logging:LogLevel:Default"] = StatsLoggingBootstrap.NormalizeLogLevelName(logLevel);
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

public sealed class StatsCorrelationMiddleware(
    RequestDelegate next,
    ILogger<StatsCorrelationMiddleware> logger,
    StatsLoggingOptions loggingOptions
)
{
    private const string CorrelationHeader = "X-Correlation-ID";
    private const int MaxCorrelationIdLength = 64;

    public async Task InvokeAsync(HttpContext context)
    {
        var correlationId = NormalizeCorrelationId(
            context.Request.Headers.TryGetValue(CorrelationHeader, out var incoming)
                ? incoming.ToString()
                : null
        );

        context.Response.Headers[CorrelationHeader] = correlationId;
        var scopeValues = new Dictionary<string, object>
        {
            ["service"] = "Stats Web",
            ["module"] = "stats-web",
        };

        if (loggingOptions.IncludeCorrelationId)
        {
            scopeValues["correlation_id"] = correlationId;
        }

        using var scope = logger.BeginScope(scopeValues);

        await next(context);
    }

    public static string NormalizeCorrelationId(string? incoming)
    {
        if (string.IsNullOrWhiteSpace(incoming))
        {
            return Guid.NewGuid().ToString("N");
        }

        var value = incoming.Trim();
        if (value.Length > MaxCorrelationIdLength)
        {
            return Guid.NewGuid().ToString("N");
        }

        foreach (var character in value)
        {
            if (!(char.IsAsciiLetterOrDigit(character) || character is '-' or '_' or '.'))
            {
                return Guid.NewGuid().ToString("N");
            }
        }

        return value;
    }
}

public static class StatsLoggingBootstrap
{
    public static StatsLoggingOptions Configure(WebApplicationBuilder builder, StatsCentralRuntime centralRuntime)
    {
        var logLevelName = Environment.GetEnvironmentVariable("LOG_LEVEL")
            ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_LEVEL")
            ?? "INFO";
        var logFormat = Environment.GetEnvironmentVariable("LOG_FORMAT")
            ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_FORMAT")
            ?? "json";
        var destination = Environment.GetEnvironmentVariable("LOG_DESTINATION")
            ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_DESTINATION")
            ?? "stdout";
        var includeCorrelationId = ParseBool(
            Environment.GetEnvironmentVariable("LOG_INCLUDE_CORRELATION_ID")
                ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_INCLUDE_CORRELATION_ID")
                ?? "true"
        );
        var redactSensitiveValues = ParseBool(
            Environment.GetEnvironmentVariable("LOG_REDACT_SENSITIVE_VALUES")
                ?? centralRuntime.LoggingDefaults.GetValueOrDefault("LOG_REDACT_SENSITIVE_VALUES")
                ?? "true"
        );

        if (!string.Equals(destination, "stdout", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                "Stats Web currently supports LOG_DESTINATION=stdout. Configure external log shipping at the container/platform layer."
            );
        }

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
            return new StatsLoggingOptions(includeCorrelationId, redactSensitiveValues, "stdout");
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
        return new StatsLoggingOptions(includeCorrelationId, redactSensitiveValues, "stdout");
    }

    public static string NormalizeLogLevelName(string value)
    {
        return value.ToUpperInvariant() switch
        {
            "DEBUG" => "Debug",
            "INFO" => "Information",
            "INFORMATION" => "Information",
            "WARN" => "Warning",
            "WARNING" => "Warning",
            "ERROR" => "Error",
            "CRITICAL" => "Critical",
            _ => "Information",
        };
    }

    private static LogLevel ParseLogLevel(string value)
    {
        return NormalizeLogLevelName(value) switch
        {
            "Debug" => LogLevel.Debug,
            "Information" => LogLevel.Information,
            "Warning" => LogLevel.Warning,
            "Error" => LogLevel.Error,
            "Critical" => LogLevel.Critical,
            _ => LogLevel.Information,
        };
    }

    private static bool ParseBool(string value)
    {
        return string.Equals(value, "true", StringComparison.OrdinalIgnoreCase)
            || string.Equals(value, "1", StringComparison.OrdinalIgnoreCase)
            || string.Equals(value, "yes", StringComparison.OrdinalIgnoreCase);
    }
}
// M0 Architecture Hardening End
