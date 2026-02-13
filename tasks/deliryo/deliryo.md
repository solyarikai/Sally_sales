Deliryo project plan

Target segmentts
Мульти фэмили офисы

Example of target website
https://oasiscapital.ru/


What I actually need related to each project is auto search driven by ai (openai api gpt4omini). So that 
1. Cheap gpt4omini generates queries related to target segments above
2. Yandex api is called with these queries to scrape results so that I got companies websites urls
3. Blacklisted websites are removed immediately (store bad results to avoid them immediately while scraping)
4. Websites are scraped (html extracted) via Crona API 
5. Scraped html is analyzed by gpt4omini (also make all prompt involved visible in prompt debug section) to make sure the company is target 


How to
Pull from remote branches efim and yandex-search-integration all necessary for yandex search integration. Get only what you need for yandex search api integration and all this data pipeline toward while merge. All crm-related changes must be preferred locally

Reuse prompts from Efim branch for companies segmentation, filtrations and other work, optimize where you see space for optimization



UI UX

In data search page there should be a project selection and after Deliryo is selected, target segments should be listed an button “run search” and then create great transparent ux to show queries being scraped in real-time. So that 
1. Progress is clear, elapsed, estimated remaining time
2. Cancel is clear
3. Results are clear and openable in a new google sheet (while progress, complete or cancel)


IMPORTANT
For test purposes, scrape no more than 100 yandex queries, and track spendings clearly



BACKLOG
1. Creating a systematic knowledge base related to a project, so that I can drop any pdf or even text via chat. And this knowledge base is considered too while running such auto-search as for Deliryo project (a little hardcoded now to get you the idea in practice)

