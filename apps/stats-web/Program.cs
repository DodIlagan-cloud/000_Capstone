// M1 - User Access Management Start
// Starts the Module 1 ASP.NET Core web frontend and exposes the Python API base URL to Razor pages.
using System.Diagnostics;
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
        StatsDataBaseUrl: builder.Configuration["StatsWeb:Proxy:StatsDataBaseUrl"] ?? centralRuntime.ModuleUrl("STATS_DATA_PORT")
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
// M9 End
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
    string StatsDataBaseUrl
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

        if (path.StartsWith("transactions/batches", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("transactions/duplicate-checks", StringComparison.OrdinalIgnoreCase)
            || path.Equals("documents", StringComparison.OrdinalIgnoreCase)
            || path.StartsWith("documents/", StringComparison.OrdinalIgnoreCase))
        {
            return proxyOptions.StatsDataBaseUrl;
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

// M9 - Stats Data and Persistence Start
public static class StatsUploadProcessingJobs
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static async Task<IResult> StartUploadProcessingJobAsync(
        HttpContext context,
        IHttpClientFactory httpClientFactory,
        StatsWebProxyOptions proxyOptions,
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
            () => RunProcessingJobAsync(jobId, tempPath, metadata, proxyOptions, httpClientFactory, loggerFactory),
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

    private static async Task RunProcessingJobAsync(
        string jobId,
        string tempPath,
        UploadProcessingMetadata metadata,
        StatsWebProxyOptions proxyOptions,
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
                    BuildValidationRequest(extractionResult)
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

    private static JsonObject BuildValidationRequest(JsonObject extractionResult)
    {
        return new JsonObject
        {
            ["extraction_id"] = extractionResult["extraction_id"]?.DeepClone(),
            ["parse_id"] = extractionResult["parse_id"]?.DeepClone(),
            ["document"] = extractionResult["document"]?.DeepClone(),
            ["document_type"] = extractionResult["document_type"]?.DeepClone(),
            ["transaction_candidates"] = extractionResult["transaction_candidates"]?.DeepClone() ?? new JsonArray(),
            ["financial_field_candidates"] = extractionResult["financial_field_candidates"]?.DeepClone() ?? new JsonArray(),
            ["section_candidates"] = extractionResult["section_candidates"]?.DeepClone() ?? new JsonArray(),
            ["entity_candidates"] = extractionResult["entity_candidates"]?.DeepClone() ?? new JsonArray(),
            ["reference_candidates"] = extractionResult["reference_candidates"]?.DeepClone() ?? new JsonArray(),
            ["line_item_candidates"] = extractionResult["line_item_candidates"]?.DeepClone() ?? new JsonArray(),
            ["installment_candidates"] = extractionResult["installment_candidates"]?.DeepClone() ?? new JsonArray(),
            ["reconciliation"] = extractionResult["reconciliation"]?.DeepClone(),
            ["findings"] = extractionResult["findings"]?.DeepClone() ?? new JsonArray()
        };
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
            ["StatsWeb:Proxy:IdentityBaseUrl"] = ModuleUrl("IDENTITY_PORT"),
            ["StatsWeb:Proxy:FileValidationBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:FileIngestionBaseUrl"] = ModuleUrl("FILE_VALIDATION_PORT"),
            ["StatsWeb:Proxy:DocumentParsingBaseUrl"] = ModuleUrl("DOCUMENT_PARSING_PORT"),
            ["StatsWeb:Proxy:TransactionExtractionBaseUrl"] = ModuleUrl("TRANSACTION_EXTRACTION_PORT"),
            ["StatsWeb:Proxy:DataValidationBaseUrl"] = ModuleUrl("DATA_VALIDATION_PORT"),
            ["StatsWeb:Proxy:StatsDataBaseUrl"] = ModuleUrl("STATS_DATA_PORT"),
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
