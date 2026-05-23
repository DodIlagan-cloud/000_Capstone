// M1 - User Access Management Start
// Supplies the configured backend API URL to the Module 1 authenticated landing page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class IndexModel(StatsApiOptions statsApiOptions, StatsWebShellOptions shellOptions) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    // M2 - Stats Web Shell Start
    // Supplies shell feature flags to the authenticated workspace.
    public bool UploadShellEnabled { get; } = shellOptions.UploadShellEnabled;

    public bool DashboardShellEnabled { get; } = shellOptions.DashboardShellEnabled;
    // M2 End
}
// M1 End
