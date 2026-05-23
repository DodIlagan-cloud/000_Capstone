// M2 - Stats Web Shell Start
// Supplies configured API settings to the email ingestion setup page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class EmailSetupModel(StatsApiOptions statsApiOptions) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');
}
// M2 End
