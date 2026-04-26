const API_PREFIX = "/v1";

const searchForm = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const limitInput = document.getElementById("limit");
const searchModeInput = document.getElementById("search-mode");
const lexicalInput = document.getElementById("lexical-weight");
const vectorInput = document.getElementById("vector-weight");
const askButton = document.getElementById("ask-btn");
const searchModeIndicatorEl = document.getElementById("search-mode-indicator");
const vectorIndicatorEl = document.getElementById("vector-indicator");
const graphIndicatorEl = document.getElementById("graph-indicator");

const searchResponseEl = document.getElementById("search-response");
const llmAnswerEl = document.getElementById("llm-answer");

let latestSearchItems = [];
const SEARCH_MODE_LABELS = {
  lexical: "Lexical",
  lexical_vector: "Lexical + Vector",
  lexical_vector_graph: "Lexical + Vector + Graph",
};

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function highlightJson(data) {
  const formatted = escapeHtml(pretty(data));
  return formatted.replace(
    /("(?:\\u[\da-fA-F]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?/g,
    (match, stringToken, keyMarker, literalToken) => {
      if (stringToken) {
        if (keyMarker) {
          return `<span class="json-key">${stringToken}</span>${keyMarker}`;
        }
        return `<span class="json-string">${stringToken}</span>`;
      }
      if (literalToken) {
        if (literalToken === "null") {
          return `<span class="json-null">${match}</span>`;
        }
        return `<span class="json-boolean">${match}</span>`;
      }
      return `<span class="json-number">${match}</span>`;
    },
  );
}

function renderJson(target, data) {
  target.innerHTML = highlightJson(data);
}

function updateSearchModeIndicator() {
  const mode = searchModeInput.value;
  const label = SEARCH_MODE_LABELS[mode] || mode;
  searchModeIndicatorEl.textContent = `Mode: ${label}`;
}

function setCapabilityIndicator(element, enabled) {
  element.classList.toggle("capability-on", enabled);
  element.classList.toggle("capability-off", !enabled);
}

function updateResultIndicators(items) {
  const hasVector = items.some((item) => {
    const vectorDebug = item?.debug?.vector || {};
    return Number(vectorDebug.weight || 0) > 0 || Number(vectorDebug.raw_score || 0) > 0;
  });
  const hasGraph = items.some((item) => Boolean(item?.payload?.graph));

  setCapabilityIndicator(vectorIndicatorEl, hasVector);
  setCapabilityIndicator(graphIndicatorEl, hasGraph);
}

async function runSearch(event) {
  if (event) {
    event.preventDefault();
  }

  const payload = {
    query: queryInput.value,
    limit: Number(limitInput.value || 10),
    search_mode: searchModeInput.value,
    lexical_weight: Number(lexicalInput.value || 0.6),
    vector_weight: Number(vectorInput.value || 0.4),
  };

  searchResponseEl.textContent = "Loading search...";
  llmAnswerEl.textContent = "";
  updateResultIndicators([]);

  try {
    const response = await fetch(`${API_PREFIX}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(pretty(body));
    }
    latestSearchItems = body.items || [];
    renderJson(searchResponseEl, body);
    updateResultIndicators(latestSearchItems);
  } catch (error) {
    searchResponseEl.textContent = `Search error:\n${String(error)}`;
    updateResultIndicators([]);
  }
}

async function askModel() {
  if (!latestSearchItems.length) {
    llmAnswerEl.textContent = "Сначала выполните поиск.";
    return;
  }

  const payload = {
    question: queryInput.value,
    items: latestSearchItems,
  };

  llmAnswerEl.textContent = "Loading model response...";

  try {
    const response = await fetch(`${API_PREFIX}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const contentType = response.headers.get("content-type") || "";
    const bodyText = await response.text();
    if (!response.ok) {
      throw new Error(bodyText || `HTTP ${response.status}`);
    }
    if (contentType.includes("application/json")) {
      try {
        const body = JSON.parse(bodyText);
        llmAnswerEl.textContent = body.answer || bodyText;
        return;
      } catch (error) {
        // Fall through to raw output.
      }
    }
    llmAnswerEl.textContent = bodyText;
  } catch (error) {
    llmAnswerEl.textContent = `Ask error:\n${String(error)}`;
  }
}

searchForm.addEventListener("submit", runSearch);
askButton.addEventListener("click", askModel);
searchModeInput.addEventListener("change", updateSearchModeIndicator);
updateSearchModeIndicator();
updateResultIndicators([]);
