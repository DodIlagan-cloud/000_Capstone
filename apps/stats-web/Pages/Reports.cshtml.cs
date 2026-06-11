// Supplies safe report configuration state to the Power BI report host shell.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class ReportsModel(
    StatsApiOptions statsApiOptions,
    StatsWebShellOptions shellOptions,
    StatsUserContextService userContext
) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    public bool ReportingConfigured { get; } = shellOptions.ReportingEmbedConfigured;

    public string EmbedMode { get; } = "AppOwnsData";

    public bool IsAdmin { get; private set; }

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
    }
}
