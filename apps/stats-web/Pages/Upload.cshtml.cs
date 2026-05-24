// M2 - Stats Web Shell Start
// Supplies configured API settings to the document-upload action page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class UploadModel(StatsApiOptions statsApiOptions, StatsWebShellOptions shellOptions) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    // M3 - File Validation Module Start
    // Exposes the validation API target so selecting a file can trigger validation automatically.
    public string FileValidationBaseUrl { get; } = shellOptions.FileValidationBaseUrl.TrimEnd('/');
    // M3 End
}
// M2 End
