// M1 - User Access Management Start
// Starts the Module 1 ASP.NET Core web frontend and exposes the Python API base URL to Razor pages.
using System.Diagnostics;
using System.Net;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddHttpClient();
builder.Services.AddSingleton(
    new StatsApiOptions(
        builder.Configuration["StatsApi:BaseUrl"]
            ?? Environment.GetEnvironmentVariable("STATS_API_BASE_URL")
            ?? throw new InvalidOperationException(
                "Configure StatsApi:BaseUrl in appsettings or STATS_API_BASE_URL before starting Stats Web."
            )
    )
);
// M2 - Stats Web Shell Start
// Starts missing local sibling APIs so the local Stats shell behaves like one app.
builder.Services.Configure<StatsLocalOrchestrationOptions>(
    builder.Configuration.GetSection("StatsWeb:LocalOrchestration")
);
builder.Services.AddHostedService<StatsLocalServiceOrchestrator>();
// M2 End
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
app.MapRazorPages();
app.Run();

public sealed record StatsApiOptions(string BaseUrl);
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
    IWebHostEnvironment environment,
    IConfiguration configuration,
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
            return response.StatusCode == HttpStatusCode.OK;
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

        var process = Process.Start(startInfo);
        if (process is null)
        {
            logger.LogWarning("Failed to start local service {ServiceName}.", service.Name);
            return;
        }

        startedProcesses.Add(process);
        logger.LogInformation("Started local service {ServiceName} as process {ProcessId}.", service.Name, process.Id);
    }

    private string ResolvePath(string configuredPath)
    {
        if (string.IsNullOrWhiteSpace(configuredPath))
        {
            return environment.ContentRootPath;
        }

        return Path.IsPathRooted(configuredPath)
            ? configuredPath
            : Path.GetFullPath(Path.Combine(environment.ContentRootPath, configuredPath));
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
