// M2 - Stats Web Shell Start
// Supplies configured API settings to the document-status shell page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class DocumentsModel(
    StatsApiOptions statsApiOptions,
    StatsWebShellOptions shellOptions,
    StatsUserContextService userContext
) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    public string StatsDataBaseUrl { get; } = shellOptions.StatsDataBaseUrl.TrimEnd('/');

    public bool IsAdmin { get; private set; }

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
    }
}
// M2 End
