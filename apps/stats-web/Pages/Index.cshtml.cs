// M1 - User Access Management Start
// Supplies the configured backend API URL to the Module 1 authenticated landing page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class IndexModel(
    StatsApiOptions statsApiOptions,
    StatsWebShellOptions shellOptions,
    StatsUserContextService userContext
) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    // M2 - Stats Web Shell Start
    // Supplies shell feature flags to the authenticated workspace.
    public bool UploadShellEnabled { get; } = shellOptions.UploadShellEnabled;

    public bool DashboardShellEnabled { get; } = shellOptions.DashboardShellEnabled;

    // Exposes safe Power BI configuration state for the dashboard shell without leaking secrets.
    public bool ReportingConfigured { get; } = shellOptions.ReportingEmbedConfigured;

    public string ReportingDefaultCurrency { get; } = NormalizeCurrency(shellOptions.ReportingDefaultCurrency);

    public bool IsAdmin { get; private set; }
    // M2 End

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
    }

    private static string NormalizeCurrency(string value)
    {
        var normalized = string.IsNullOrWhiteSpace(value) ? "NZD" : value.Trim().ToUpperInvariant();
        return normalized is "NZD" or "PHP" or "AUD" or "USD" ? normalized : "NZD";
    }
}
// M1 End
