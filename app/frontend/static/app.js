const API_PREFIX = "/v1";

const searchForm = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const limitInput = document.getElementById("limit");
const lexicalInput = document.getElementById("lexical-weight");
const vectorInput = document.getElementById("vector-weight");
const askButton = document.getElementById("ask-btn");

const searchResponseEl = document.getElementById("search-response");
const llmAnswerEl = document.getElementById("llm-answer");
const llmThinkEl = document.getElementById("llm-think");

let latestSearchItems = [];

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

async function runSearch(event) {
  if (event) {
    event.preventDefault();
  }

  const payload = {
    query: queryInput.value,
    limit: Number(limitInput.value || 10),
    lexical_weight: Number(lexicalInput.value || 0.6),
    vector_weight: Number(vectorInput.value || 0.4),
  };

  searchResponseEl.textContent = "Loading search...";
  llmAnswerEl.textContent = "";
  llmThinkEl.textContent = "";

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
    searchResponseEl.textContent = pretty(body);
  } catch (error) {
    searchResponseEl.textContent = `Search error:\n${String(error)}`;
  }
}

async function askModel() {
  if (!latestSearchItems.length) {
    llmAnswerEl.textContent = "Сначала выполните поиск.";
    llmThinkEl.textContent = "";
    return;
  }

  const payload = {
    question: queryInput.value,
    items: latestSearchItems,
  };

  llmAnswerEl.textContent = "Loading model response...";
  llmThinkEl.textContent = "";

  try {
    const response = await fetch(`${API_PREFIX}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(pretty(body));
    }
    llmAnswerEl.textContent = body.answer || "";
    llmThinkEl.textContent = body.think || "";
  } catch (error) {
    llmAnswerEl.textContent = `Ask error:\n${String(error)}`;
    llmThinkEl.textContent = "";
  }
}

searchForm.addEventListener("submit", runSearch);
askButton.addEventListener("click", askModel);

