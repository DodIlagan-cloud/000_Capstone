// M2 - Stats Web Shell Start
// Supplies configured API settings to the document-upload action page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class UploadModel(
    StatsApiOptions statsApiOptions,
    StatsWebShellOptions shellOptions,
    StatsUserContextService userContext
) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    // M3 - File Validation Module Start
    // Exposes the validation API target so selecting a file can trigger validation automatically.
    public string FileValidationBaseUrl { get; } = shellOptions.FileValidationBaseUrl.TrimEnd('/');

    // Exposes the ingestion API target for validation-gated handoff to common processing storage.
    public string FileIngestionBaseUrl { get; } = shellOptions.FileIngestionBaseUrl.TrimEnd('/');
    // M3/M4 End

    // M5 - Document Parsing Module Start
    // Exposes the parsing API target for the validate -> ingest -> parse upload flow.
    public string DocumentParsingBaseUrl { get; } = shellOptions.DocumentParsingBaseUrl.TrimEnd('/');
    // M5/M6 End

    // M8 - Data Validation Module Start
    // Exposes extraction and validation API targets for the M5 -> M7 -> M8 upload flow.
    public string TransactionExtractionBaseUrl { get; } = shellOptions.TransactionExtractionBaseUrl.TrimEnd('/');

    public string DataValidationBaseUrl { get; } = shellOptions.DataValidationBaseUrl.TrimEnd('/');
    // M8 End

    // M9 - Stats Data and Persistence Start
    // Exposes the Stats Data save target for reviewed validation results.
    public string StatsDataBaseUrl { get; } = shellOptions.StatsDataBaseUrl.TrimEnd('/');
    // M9 End

    public bool IsAdmin { get; private set; }

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
    }
}
// M2 End
