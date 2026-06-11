// M2/M5/M7/M11 - Classification Administration Start
// Supplies classification configuration to the admin recognition settings page.
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Stats.Web.Pages.Admin;

public class ClassificationsModel(
    StatsApiOptions statsApiOptions,
    StatsUserContextService userContext,
    IHttpClientFactory httpClientFactory,
    StatsWebProxyOptions proxyOptions,
    StatsInternalApiOptions internalApiOptions
) : PageModel
{
    private const string InternalApiKeyHeaderName = "X-Stats-Internal-Key";
    private const string VocabularyFileName = "document-classification.vocabulary.json";
    private const string RulesFileName = "document-classification.rules.json";
    private const string TransactionVocabularyFileName = "transaction-classification.vocabulary.json";
    private const string SpendingRulesFileName = "spending-category.rules.json";

    public string ApiBaseUrl { get; } = statsApiOptions.BaseUrl.TrimEnd('/');

    public IReadOnlyList<DocumentVocabularyEntry> DocumentVocabulary { get; private set; } = [];

    public IReadOnlyList<DocumentRuleEntry> DocumentRules { get; private set; } = [];

    public IReadOnlyList<LabelGroupEntry> TransactionLabels { get; private set; } = [];

    public IReadOnlyList<LabelGroupEntry> SpendingLabels { get; private set; } = [];

    public IReadOnlyList<RecognitionSuggestionEntry> PendingSuggestions { get; private set; } = [];

    public string? ConfigurationWarning { get; private set; }

    public string? SaveMessage { get; private set; }

    public bool IsAdmin { get; private set; }

    public int DocumentTypeCount => DocumentVocabulary.Count;

    public int DocumentSubtypeCount => DocumentVocabulary.Sum(entry => entry.Subtypes.Count);

    public int DocumentRuleCount => DocumentRules.Count;

    public async Task OnGetAsync()
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        await LoadConfigurationAsync();
    }

    public async Task<IActionResult> OnPostSaveTransactionLabelAsync(
        string originalLabel,
        string label,
        string values
    )
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await SaveRecognitionLabelAsync("transaction", originalLabel, label, values);
            SaveMessage = "Transaction label saved.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Transaction label could not be saved: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostSaveSpendingLabelAsync(
        string originalLabel,
        string label,
        string values
    )
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await SaveRecognitionLabelAsync("spending", originalLabel, label, values);
            SaveMessage = "Spending label saved.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Spending label could not be saved: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostSaveDocumentLabelAsync(
        string originalLabel,
        string label,
        string values
    )
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await SaveDocumentLabel(originalLabel, label, values);
            SaveMessage = "Document type saved.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Document type could not be saved: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostDeleteDocumentLabelAsync(string label)
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await DeleteDocumentLabel(label);
            SaveMessage = "Document type deleted.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Document type could not be deleted: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostDeleteDocumentRuleAsync(string reasonCode)
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await DeleteRecognitionRuleAsync("document", reasonCode);
            SaveMessage = "Recognition rule deleted.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Recognition rule could not be deleted: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostSaveDocumentRuleAsync(
        string originalReasonCode,
        string targetLabel,
        string targetSubtype,
        string reasonCode,
        string requiredAny,
        string signals,
        double minimumScore
    )
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await SaveRecognitionRuleAsync("document", originalReasonCode, targetLabel, targetSubtype, reasonCode, requiredAny, signals, minimumScore);
            SaveMessage = "Recognition rule saved.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Recognition rule could not be saved: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostDeleteTransactionLabelAsync(string label)
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await DeleteTransactionLabel(label);
            SaveMessage = "Transaction label deleted.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Transaction label could not be deleted: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostDeleteSpendingLabelAsync(string label)
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await DeleteSpendingLabel(label);
            SaveMessage = "Spending label deleted.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Spending label could not be deleted: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    public async Task<IActionResult> OnPostReviewSuggestionAsync(string suggestionId, string action, string reviewNote)
    {
        IsAdmin = await userContext.IsAdminAsync(HttpContext);
        if (!IsAdmin)
        {
            return StatusCode(StatusCodes.Status403Forbidden);
        }

        try
        {
            await ReviewRecognitionSuggestionAsync(suggestionId, action, reviewNote);
            SaveMessage = string.Equals(action, "approve", StringComparison.OrdinalIgnoreCase)
                ? "Suggestion approved."
                : "Suggestion rejected.";
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or ArgumentException)
        {
            ConfigurationWarning = $"Suggestion could not be reviewed: {error.Message}";
        }

        await LoadConfigurationAsync();
        if (IsAsyncSaveRequest())
        {
            return new JsonResult(new
            {
                ok = string.IsNullOrWhiteSpace(ConfigurationWarning),
                message = SaveMessage ?? ConfigurationWarning,
            });
        }

        return Page();
    }

    private async Task LoadConfigurationAsync()
    {
        try
        {
            var activeSettings = await GetActiveRecognitionSettingsAsync();
            DocumentVocabulary = LoadVocabulary(activeSettings, "document_vocabulary", "document_subtypes");
            DocumentRules = LoadRules(activeSettings, "document_rules");
            TransactionLabels = LoadLabels(activeSettings, "transaction_vocabulary", "transaction_subtypes");
            SpendingLabels = LoadLabels(activeSettings, "spending_vocabulary", "spending_subcategories");
            PendingSuggestions = await GetPendingSuggestionsAsync();
        }
        catch (Exception error) when (error is HttpRequestException or TaskCanceledException or JsonException or InvalidOperationException)
        {
            ConfigurationWarning = $"Recognition settings could not be loaded: {error.Message}";
            DocumentVocabulary = [];
            DocumentRules = [];
            TransactionLabels = [];
            SpendingLabels = [];
            PendingSuggestions = [];
        }
    }

    private async Task<JsonObject> GetActiveRecognitionSettingsAsync()
    {
        var client = httpClientFactory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/active"
        );
        AddStatsDataAdminHeader(request);
        using var response = await client.SendAsync(request, HttpContext.RequestAborted);
        response.EnsureSuccessStatusCode();
        using var stream = await response.Content.ReadAsStreamAsync(HttpContext.RequestAborted);
        var json = await JsonNode.ParseAsync(stream, cancellationToken: HttpContext.RequestAborted) as JsonObject;
        return json ?? throw new InvalidOperationException("Recognition settings API returned an empty response.");
    }

    private async Task SaveRecognitionLabelAsync(string scope, string originalLabel, string label, string values)
    {
        var client = httpClientFactory.CreateClient();
        var payload = new
        {
            scope,
            original_label = originalLabel ?? string.Empty,
            label,
            values = SplitCsv(values),
        };
        using var response = await SendStatsDataAdminJsonAsync(
            client,
            HttpMethod.Post,
            "/api/v1/admin/recognition-settings/labels",
            payload
        );
        await EnsureRecognitionResponseAsync(response);
    }

    private Task SaveDocumentLabel(string originalLabel, string label, string values)
    {
        return SaveRecognitionLabelAsync("document", originalLabel, label, values);
    }

    private Task DeleteDocumentLabel(string label)
    {
        return DeleteRecognitionLabelAsync("document", label);
    }

    private Task DeleteTransactionLabel(string label)
    {
        return DeleteRecognitionLabelAsync("transaction", label);
    }

    private Task DeleteSpendingLabel(string label)
    {
        return DeleteRecognitionLabelAsync("spending", label);
    }

    private async Task DeleteRecognitionLabelAsync(string scope, string label)
    {
        if (string.Equals(label?.Trim(), "Unknown", StringComparison.OrdinalIgnoreCase)
            || string.Equals(label?.Trim(), "Uncategorized", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("The Unknown fallback label cannot be deleted.");
        }

        var client = httpClientFactory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Delete,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/labels"
        )
        {
            Content = JsonContent.Create(new { scope, label }),
        };
        AddStatsDataAdminHeader(request);
        using var response = await client.SendAsync(request, HttpContext.RequestAborted);
        await EnsureRecognitionResponseAsync(response);
    }

    private async Task DeleteRecognitionRuleAsync(string scope, string reasonCode)
    {
        var client = httpClientFactory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Delete,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/rules"
        )
        {
            Content = JsonContent.Create(new { scope, reason_code = reasonCode }),
        };
        AddStatsDataAdminHeader(request);
        using var response = await client.SendAsync(request, HttpContext.RequestAborted);
        await EnsureRecognitionResponseAsync(response);
    }

    private async Task SaveRecognitionRuleAsync(
        string scope,
        string originalReasonCode,
        string targetLabel,
        string targetSubtype,
        string reasonCode,
        string requiredAny,
        string signals,
        double minimumScore
    )
    {
        var client = httpClientFactory.CreateClient();
        var payload = new
        {
            scope,
            original_reason_code = originalReasonCode ?? string.Empty,
            target_label = targetLabel,
            target_subtype = targetSubtype,
            reason_code = reasonCode,
            required_any = SplitCsv(requiredAny),
            signals = SplitCsv(signals),
            minimum_score = minimumScore,
        };
        using var response = await SendStatsDataAdminJsonAsync(
            client,
            HttpMethod.Post,
            "/api/v1/admin/recognition-settings/rules",
            payload
        );
        await EnsureRecognitionResponseAsync(response);
    }

    private async Task ReviewRecognitionSuggestionAsync(string suggestionId, string action, string reviewNote)
    {
        var client = httpClientFactory.CreateClient();
        var currentUser = await userContext.GetCurrentUserAsync(HttpContext);
        var payload = new
        {
            action,
            admin_user_id = currentUser?.Email ?? "admin",
            review_note = reviewNote ?? string.Empty,
        };
        using var response = await SendStatsDataAdminJsonAsync(
            client,
            HttpMethod.Patch,
            $"/api/v1/admin/recognition-settings/suggestions/{Uri.EscapeDataString(suggestionId)}",
            payload
        );
        await EnsureRecognitionResponseAsync(response);
    }

    private async Task<IReadOnlyList<RecognitionSuggestionEntry>> GetPendingSuggestionsAsync()
    {
        var client = httpClientFactory.CreateClient();
        using var request = new HttpRequestMessage(
            HttpMethod.Get,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}/api/v1/admin/recognition-settings/suggestions?status=pending&limit=50"
        );
        AddStatsDataAdminHeader(request);
        using var response = await client.SendAsync(request, HttpContext.RequestAborted);
        response.EnsureSuccessStatusCode();
        using var stream = await response.Content.ReadAsStreamAsync(HttpContext.RequestAborted);
        var json = await JsonNode.ParseAsync(stream, cancellationToken: HttpContext.RequestAborted) as JsonObject;
        var suggestions = json?["suggestions"] as JsonArray;
        if (suggestions is null)
        {
            return [];
        }

        return suggestions
            .OfType<JsonObject>()
            .Select(suggestion => new RecognitionSuggestionEntry(
                Text(suggestion, "suggestion_id", string.Empty),
                Text(suggestion, "source_module", string.Empty),
                Text(suggestion, "source_candidate_id", string.Empty),
                ToDisplayLabel(Text(suggestion, "current_document_type", "unknown")),
                ToDisplayLabel(Text(suggestion, "current_document_subtype", "unknown")),
                ToDisplayLabel(Text(suggestion, "current_transaction_type", "unknown")),
                ToDisplayLabel(Text(suggestion, "current_transaction_subtype", "unknown")),
                ToDisplayLabel(Text(suggestion, "current_spending_category", "uncategorized")),
                ToDisplayLabel(Text(suggestion, "current_spending_subcategory", "unknown")),
                ToDisplayLabel(Text(suggestion, "suggested_document_type", "unknown")),
                ToDisplayLabel(Text(suggestion, "suggested_document_subtype", "unknown")),
                ToDisplayLabel(Text(suggestion, "suggested_transaction_type", "unknown")),
                ToDisplayLabel(Text(suggestion, "suggested_transaction_subtype", "unknown")),
                ToDisplayLabel(Text(suggestion, "suggested_spending_category", "uncategorized")),
                ToDisplayLabel(Text(suggestion, "suggested_spending_subcategory", "unknown")),
                NullableDouble(suggestion, "suggestion_confidence"),
                Text(suggestion, "suggestion_source", "unknown"),
                Text(suggestion, "suggestion_evidence_ref", string.Empty)))
            .Where(suggestion => suggestion.SuggestionId.Length > 0)
            .ToArray();
    }

    private static async Task EnsureRecognitionResponseAsync(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        var detail = FriendlyRecognitionError(
            response.StatusCode,
            await response.Content.ReadAsStringAsync()
        );
        throw new InvalidOperationException(detail);
    }

    private async Task<HttpResponseMessage> SendStatsDataAdminJsonAsync(
        HttpClient client,
        HttpMethod method,
        string path,
        object payload
    )
    {
        using var request = new HttpRequestMessage(
            method,
            $"{proxyOptions.StatsDataBaseUrl.TrimEnd('/')}{path}"
        )
        {
            Content = JsonContent.Create(payload),
        };
        AddStatsDataAdminHeader(request);
        return await client.SendAsync(request, HttpContext.RequestAborted);
    }

    private void AddStatsDataAdminHeader(HttpRequestMessage request)
    {
        if (!string.IsNullOrWhiteSpace(internalApiOptions.InternalApiKey))
        {
            request.Headers.TryAddWithoutValidation(InternalApiKeyHeaderName, internalApiOptions.InternalApiKey);
        }
    }

    private static string FriendlyRecognitionError(System.Net.HttpStatusCode statusCode, string responseBody)
    {
        if (statusCode == System.Net.HttpStatusCode.Forbidden)
        {
            return "Administrator access is required.";
        }

        if (statusCode == System.Net.HttpStatusCode.NotFound)
        {
            return "This review item is no longer available. Refresh the items to review and try again.";
        }

        var detail = ExtractRecognitionDetail(responseBody);
        if (string.IsNullOrWhiteSpace(detail))
        {
            return "Recognition settings could not be updated. Refresh the page and try again.";
        }

        if (detail.Contains("not found", StringComparison.OrdinalIgnoreCase)
            || detail.Contains("404", StringComparison.OrdinalIgnoreCase))
        {
            return "This review item is no longer available. Refresh the items to review and try again.";
        }

        if (detail.TrimStart().StartsWith('{') || detail.Contains("Traceback", StringComparison.OrdinalIgnoreCase))
        {
            return "Recognition settings could not be updated. Refresh the page and try again.";
        }

        return detail;
    }

    private static string ExtractRecognitionDetail(string responseBody)
    {
        if (string.IsNullOrWhiteSpace(responseBody))
        {
            return string.Empty;
        }

        try
        {
            using var document = JsonDocument.Parse(responseBody);
            var root = document.RootElement;
            foreach (var propertyName in new[] { "detail", "message", "title" })
            {
                if (root.TryGetProperty(propertyName, out var property))
                {
                    return property.ValueKind == JsonValueKind.String
                        ? property.GetString() ?? string.Empty
                        : property.ToString();
                }
            }
        }
        catch (JsonException)
        {
            return responseBody.Trim();
        }

        return responseBody.Trim();
    }

    private static IReadOnlyList<DocumentVocabularyEntry> LoadVocabulary(JsonObject source, string sectionName, string subtypeKey)
    {
        var subtypes = source[sectionName]?[subtypeKey] as JsonObject;
        if (subtypes is null)
        {
            return [];
        }

        return subtypes
            .Select(entry => new DocumentVocabularyEntry(
                ToDisplayLabel(entry.Key),
                (entry.Value as JsonArray)?.Select(value => ToDisplayLabel(value?.GetValue<string>() ?? string.Empty)).Where(value => value.Length > 0).ToArray() ?? []))
            .OrderBy(entry => entry.DocumentType)
            .ToArray();
    }

    private static IReadOnlyList<DocumentRuleEntry> LoadRules(JsonObject source, string sectionName)
    {
        var rules = source[sectionName]?["rules"] as JsonArray;
        if (rules is null)
        {
            return [];
        }

        return rules
            .OfType<JsonObject>()
            .Select(rule => new DocumentRuleEntry(
                ToDisplayLabel(Text(rule, "document_type", "unknown")),
                ToDisplayLabel(Text(rule, "document_subtype", "unknown")),
                Text(rule, "reason_code", "UNSPECIFIED_RULE"),
                ReadStringArray(rule, "required_any"),
                ReadStringArray(rule, "signals"),
                Double(rule, "minimum_score")))
            .OrderBy(rule => rule.DocumentType)
            .ThenBy(rule => rule.DocumentSubtype)
            .ToArray();
    }

    private static IReadOnlyList<LabelGroupEntry> LoadLabels(JsonObject source, string sectionName, string subtypeKey)
    {
        var subtypes = source[sectionName]?[subtypeKey] as JsonObject;
        if (subtypes is null)
        {
            return [];
        }

        return subtypes
            .Select(entry => new LabelGroupEntry(
                ToDisplayLabel(entry.Key),
                (entry.Value as JsonArray)?.Select(value => ToDisplayLabel(value?.GetValue<string>() ?? string.Empty)).Where(value => value.Length > 0).ToArray() ?? []))
            .OrderBy(entry => entry.Label)
            .ToArray();
    }

    private static string[] SplitCsv(string values)
    {
        return (values ?? string.Empty)
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(value => value.Length > 0)
            .ToArray();
    }

    private static string Text(JsonObject source, string propertyName, string fallback)
    {
        return source[propertyName]?.GetValue<string>() ?? fallback;
    }

    private static double Double(JsonObject source, string propertyName)
    {
        return source[propertyName]?.GetValue<double>() ?? 0;
    }

    private static double? NullableDouble(JsonObject source, string propertyName)
    {
        return source[propertyName] is null ? null : source[propertyName]?.GetValue<double>();
    }

    private static IReadOnlyList<string> ReadStringArray(JsonObject source, string propertyName)
    {
        return source[propertyName] is JsonArray values
            ? values.Select(value => value?.GetValue<string>() ?? string.Empty).Where(value => value.Length > 0).ToArray()
            : [];
    }

    private static string ToDisplayLabel(string value)
    {
        var words = value.Split('_', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return string.Join(" ", words.Select(word => word.Length == 0 ? word : string.Concat(char.ToUpperInvariant(word[0]), word[1..]))).Trim();
    }

    private bool IsAsyncSaveRequest()
    {
        return string.Equals(Request.Headers["X-Stats-Async-Save"].ToString(), "true", StringComparison.OrdinalIgnoreCase);
    }
}

public sealed record DocumentVocabularyEntry(string DocumentType, IReadOnlyList<string> Subtypes);

public sealed record LabelGroupEntry(string Label, IReadOnlyList<string> Values);

public sealed record DocumentRuleEntry(
    string DocumentType,
    string DocumentSubtype,
    string ReasonCode,
    IReadOnlyList<string> RequiredAny,
    IReadOnlyList<string> Signals,
    double MinimumScore)
{
    public double MinimumMatchStrength => MinimumScore;
}

public sealed record RecognitionSuggestionEntry(
    string SuggestionId,
    string SourceModule,
    string SourceCandidateId,
    string CurrentDocumentType,
    string CurrentDocumentSubtype,
    string CurrentTransactionType,
    string CurrentTransactionSubtype,
    string CurrentSpendingCategory,
    string CurrentSpendingSubcategory,
    string SuggestedDocumentType,
    string SuggestedDocumentSubtype,
    string SuggestedTransactionType,
    string SuggestedTransactionSubtype,
    string SuggestedSpendingCategory,
    string SuggestedSpendingSubcategory,
    double? SuggestionConfidence,
    string SuggestionSource,
    string SuggestionEvidenceRef);
// M2/M5/M7/M11 End
