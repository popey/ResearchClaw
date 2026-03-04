# Research & Academic News

- name: news
- description: Fetch and summarize the latest research news, academic announcements, and science reporting from trusted sources.
- emoji: 📰
- requires: []

## News Sources

| Category | Source | URL |
|----------|--------|-----|
| AI/ML | AI News | https://www.artificialintelligence-news.com/ |
| Science | Science Daily | https://www.sciencedaily.com/ |
| Technology | TechCrunch AI | https://techcrunch.com/category/artificial-intelligence/ |
| Academic | Nature News | https://www.nature.com/news |
| Academic | Science News | https://www.science.org/news |
| CS Research | Papers With Code | https://paperswithcode.com/ |
| Preprints | arxiv Sanity | https://arxiv-sanity-lite.com/ |
| Policy | Science Policy | https://sciencepolicy.colorado.edu/ |

## How to Use

1. Open the news source in the browser:
   ```json
   {"action": "open", "url": "https://www.sciencedaily.com/"}
   ```

2. Take a snapshot to see current headlines:
   ```json
   {"action": "snapshot"}
   ```

3. Extract and summarize the top stories with titles, brief descriptions, and links.

4. For deeper analysis, navigate to individual articles and extract key points.

## Output Format

Present news summaries in this format:

```
📰 **[Category] Source Name** — [Date]

1. **Title of Article**
   Summary of key findings/announcements (2-3 sentences)
   🔗 [Link]

2. **Title of Article**
   Summary...
   🔗 [Link]
```

## Rules

- Always attribute the source
- Provide direct links to original articles
- Focus on factual reporting, avoid editorializing
- For research papers mentioned in news, also check the original paper on arxiv if available
- Summarize in the user's preferred language
