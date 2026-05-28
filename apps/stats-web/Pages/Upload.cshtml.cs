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

    // Exposes the ingestion API target for validation-gated handoff to common processing storage.
    public string FileIngestionBaseUrl { get; } = shellOptions.FileIngestionBaseUrl.TrimEnd('/');
    // M3/M4 End

    // M5 - Document Parsing Module Start
    // Exposes the parsing API target for the validate -> ingest -> parse upload flow.
    public string DocumentParsingBaseUrl { get; } = shellOptions.DocumentParsingBaseUrl.TrimEnd('/');
    // M5/M6 End
}
// M2 End
