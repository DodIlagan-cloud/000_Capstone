// M1 - User Access Management Start
// Starts the Module 1 ASP.NET Core web frontend and exposes the Python API base URL to Razor pages.
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddSingleton(
    new StatsApiOptions(
        builder.Configuration["StatsApi:BaseUrl"]
            ?? Environment.GetEnvironmentVariable("STATS_API_BASE_URL")
            ?? throw new InvalidOperationException(
                "Configure StatsApi:BaseUrl in appsettings or STATS_API_BASE_URL before starting Stats Web."
            )
    )
);

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseStaticFiles();
app.UseRouting();
app.MapRazorPages();
app.Run();

public sealed record StatsApiOptions(string BaseUrl);
// M1 End
