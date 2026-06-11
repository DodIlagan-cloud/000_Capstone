// M1 - User Access Management Start
// Supplies the configured backend API URL to the Module 1 user management page.
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages;

public class UsersModel(StatsApiOptions statsApiOptions, StatsUserContextService userContext) : PageModel
{
    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    public bool IsAdmin { get; private set; }

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
    }
}
// M1 End
