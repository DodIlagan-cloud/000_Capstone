// M2 - Stats Web Shell Start
// Supplies configured API settings to the document-upload action page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class UploadModel(StatsApiOptions statsApiOptions) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');
}
// M2 End
