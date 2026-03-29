-----------
the default smarltead campaign creation flow:

user connects --> mcp greets with required mcp token to start work!!!! before mcp token provided, mcp mustn't response anything else besides "go sign up here: <sign up link>, provide mcp key"

after mcp key is provided mcp tells user the default flow: "let's launch smarltead campaign for the segments you need", but first provide me the keys: apollo to source the data, openai to do ai stuff and smartlead to launch the campsigns baby, and apify to scrape websites" (move apify also to setup not to use our)
until apollo, openai, smarltead and apify keys are not setup user is told to setup keys in the ui <link to setup keys>

after user setup keys, mcp asks "which segments we'll launch today bro?" - btw can mcp know about this after user sets the keys in ui and yet wrote nothing to mcp - can mcp write itself? as db already will have the keys (the keys are set only via ui for security purposes). then user (imagine user in hurry and rush) asks to gather 2 segments (like in conversation 01_new_user_easystaff.json), but wise mcp knows that project and offer must be passed first, so mcp asks: before launching the pipeline (as user's query to gather segments must trigger launching the pipeline flow and pipeline flow is companies apollo->scraping, classifying, filtering-->people apollo -> smalrtead campaing creation with perfect sequences and perfect seetings and test email sent to the user's email) mcp asks "what are the offer we're working with? provide a website at least"

then user provides easystaff.io and that's must be enough for mcp to create project from the website name easysatff, scrape website and take the offer from there and proceed with "easystaff project data is here <link to the project page>, before launching the pipeline also tell me "have you launched campaigns for this project before"?

then user answers that campaigns including "petr" was launched before for that project

Before running the pipeline mcp must align essential filters for companies search: as business segment and geo already provided by user, company size remaining. Make mcp smart enough to understand from easystaff offer that their target companies are 10-200 size (matching apollo filters, right?) ,add such smart logic and test it too!*as well as everything else in this document 

then mcp answers "adding contacts from this campaings to blacklist and running 2 pipelines (as user requested 2 segments): <link to pipelines page> (to see the list of pipelines and easily dive into each) and list apollo filters applied in readable pretty format

!! ensure that replies processing also running in background after user told which campsings were previously used so that further questins about "show warm replies, which leads need followups?"

after all contacts and conversations from previously used campaigns are loaded, mcp must message user with link to crm to view the contacts from the campaigns - filtered view by project filter applied in the top left corner and taken from query string obviously (again question can mcp write to user itself without trigger by user?  
 *however, for initial start of usage there won’t be any other projects for this new user, but the ux flow must be proper from the very beginning so that user has the correct impression how this perfect system works

After gathering launched mcp must ask user (essential to ask before creating smarted campaigns to create them with email accounts initially for the test email able to be sent) like “while pipelines are gathering your target icp, tell which email accounts to use for each pipeline?” (2 pipelines implies 2 smarted campaigns so there might be different email accounts for each) 

Then user answers “use Eleonora accounts from the previous campaigns (campaigns the user provided as “launched before for this project”) for both campaigns / pipelines (both variations must be approoairte and tested!!!!! Must test variations of user messages keeping the intent you remember?) 

After target companies are gathered for each pipeline mcp must notify user about stats and then tell the the people filters applied (by default clevel but even better to adjust to the offer, add a gpt4omini mapper here too if it’s essential to adjust filter to the offer) and share links to the exact pipeline page when sharing info/updtes about the pipeline

After people are gathered for each pipeline smartlead campaign must be created with perfect sequence adjusted to the offer, test email sent and mcp must write to user:
1. Smartlead campaign link: <link>
2. CRM contacts link: <link to crm with filters in query string> (filtered by newly created campaign) 
    1. Probably new requirements for ui but essential! after clicking on each contact in crm, conversation first must be shown (send and planned with clear uiux separation, make it clear and minimalistic, apple and telegram style) and also !!!!!!! tab with reasoning must be shown where the same reasoning about company segment and why it’s target is shown as in the pipiline page while clicking on each company row
3. Check your inbox at <user’s email>
4. Approve the launch

Then user approves and the campaigns getting launched (change this part in test as well any other parts to correspond to the requirements stated here for the default smarltead campaign creation flow.
Then users asks about warm replies and leads to followup and everything else according to existing 01_new_user_easystaff.json

essential considerations
A mcp flow must be simple - only one flow-blocking question each time, nothing else
B How initial filters are applied? how exploration phase is done to find out perfect filters to apply in apollo for the user’s query? Remember there was a plan (and maybe even built) to make several (up to 5) enrichment calls for the most target companies of the initial apollo companies search call is done to get as many apollo fitlers providing target companies as possible. I need to get at least 100 contacts to be in each campaign for this test flow, up to 3 contacts for a company. Of course all contacts must be from target companies. Build god level exploration approach that costs no more than 5 apollo credits on enrichment calls (not counting search calls themselves) and providing best apollo filters as a result. Best apollo filters = filters that provide maximum of target companies. Companies websites will be further scraped and analyzed according to the pipeline and conversion % from apollo company to real target company is usually not so high, that’s why it’s the tough point and usually the bottleneck, so that’s a great leverage for the result , so implement god-level. So possible implementation here is getting initial list from apollo search companies endpoint, scraping websites with apify proxy as usual, picking top 5 targets (by yourself = opus = by user’ agent running mcp in Claude code for instance — or better on mcp level via gpt4omini? Decide yourself , speed is important here, also answer question “should these initial companies be sown in pipeline ? Probably yes and there is suitable entity for this called iteration in pipeline. So that first pipeline with “draft filters for research” and second pipeline with extended filters from the reverse engineering. What about ui - in ui all iterations must be selected by default and in apollo filters the recently applied filters must be shown (meaning for iteration 2 in this sense — but against’s my vision that seems to work well, but I want you to think as god and create the best approach to maximize the result in terms of target companies number) according to what user asked and of course not competitors, then calling enrichment endpoint from apollo to reveal all their apollo labels.
C Ensure all browser ui steps tell user full transparency and clear picture of happening: for example, with links including filters all filters must be applied properly = as expected from the business logic, 
D be testing god , test real browser making screenshots 

steps
1. adjust test flow in 01_new_user_easystaff.json to start exactly as I described above and mcp behaves exactly as I described above
2. Build everything obviously missing according to the default smarltead campaign creation flow requirements above. 
    1. Build exploration phase as god first, at least industry, keywords filters for busines segment and extended by reverse engineering from the definitely target companies by apollo labeling
    2. Build everything else mentioned above but missed in the existing mcp logic
3. Test only this test but loop (test—>fix—> test—>fix—>etc) it perfectly until 100% done, don’t stop until done
4. Also it’s essential and  required to test quality of the "target” companies and people found and проверить качество компаний и применяемых фильтров, ensure competitors are excluding on the gpt4omini prompt level and in the final result. Test final selected companies and contacts yourself = via opus (split to batches for parallel multi-agents review) to answer the question “is this company and contact real icp for EasyStaff payroll offer?” 100 contacts must be in each campaign, up to 3 contacts per company



backlog
1. remove useless columns from crm, don't affect main app, remove for mcp only - never affect main app, you remember?
2. add tokens count of mcp somehow, decide yourself how's better to count usage of mcp itself, account page must show spendings on all connected tools: for default flow essential are openai, apify, apollo and mcp itself (smartlead doesn't have costs per api usage). calculate how many tokens will be spent to launch 20 campaings per month (estimate each campaign is gathering 1000 contacst, so 20,000 contacts gathering with the definitions of targets, adjusting targets companies, roles, sequences) must be default scubction covered by $20/mo. calculate as god, i will connect stripe after 


-------

❯ test the quality of exploration phase first seprarely , focus on quality and speed on achiving 100 target contacts  
up to 3 for each target copany for the test cases descrbived! contacts must be from mew companies considering         
blacklist you remember  


❯ add to your test frameworks thi quality test sysmtematically! act as testing god to test gathering target       
  companies according to the given kpis from the user prompts     


   achieve at least 95% accuracy (comparing  gpt4omni labeling with your real labeling)  on initial companies saerch   
adjusting gpt4omini prompt until required accuracy achieved to furher use the improved prompt    

 scraper must use apify residential proxy !!!! then apply any postprocessing to extract text only, act as god    
  for this purpose, see how scraper is built in the main app     


  ❯ what is confidence???/ confidence seems like total shit, gpt4omnin is shit in providing confidence, focus on    
  via negativa approach and proper segmentaion, exclude confiedence from prompt , ui , everywhere — it's only       
  confusing          

  ❯ on this small volume of initial search make gpt4omini vs your claude opinion align 100% before going next to    
  iteration 2 with: 1. extended apollo filters from the findings, 2. updated gpt4omini prompt with better accuracy  


  ❯ also make sure you didn't simply hardcode gpt prompts and that it's genrated from scratch and further updated   
  according the feedback ,test reality always , test real sustem    


    ❯ document testing of exploration phase in tests dir too                                                            
  ❯ also write files with timestampts in tmp dir in tests dir for both exloration tests and whole test you wil be     
  doing further  

    ❯ document testing of exploration phase in tests dir too                                                            
  ❯ also write files with timestampts in tmp dir in tests dir for both exloration tests and whole test you wil be     
  doing further  


  ❯ analyze yourself how do you find the exploration test results??? the more flters like keywords or industries    
  applied the more companies are provided by apollo. of course the industries and keywords must be rlevant to         
  user's segment description but need to build god level system here that takes as much as possible of relevant     
  filters to provide more companies for analysis as resutls --> more target companies in the end. test exploration    
  phase at least 10 times with deffirent approaches for fitlers extension and choose the best, think generalyl!!!!! 
   not tovias and hardcode for my particuklar test case but solve on the any general level    

   ❯ load map of apollo keywords and industries filters !!!!!! to use it effectively from the very start when user   
  provided a prompt to gather companies   



You see, I want prompts to work properly without knowing anything hard-coded about the project. But I know, like, I provided you this 10 to 200, like, expected result. So make sure your prompts have this, like, good reasoning. Of course, the user, according to the flow, user can decline your suggestion about the size, and user can provide his vision about the size, and you should consider it, right? So make sure that also works as essential. However, for this stuff specifically, it's obvious that it SMB, so, like, as more complex, so in this prompt, just create this SMB bottleneck, SMB, I mean, threshold of 200 employees, as companies above it definitely solved such pains as, like, as payroll, you see? So that would be a sweet spot, that's about sweet spotting. Also, for a good and unbiased exploration test, include all other segments for all other projects mentioned in tests, the directory in conversations. There are the fashion people project on social project, gathering for the fashion people, fashion Italy brands and foreign social gathering, let's say, creator platforms, social influencers platforms from UK. So test your exploration. I want this exploration phase to work perfectly to adapt to each case properly, without bias, without any hard code. So iterate prompts until the error is minimum. You know the right answers. Don't hard code them. Just test different approaches. I don't know, 10, 50, 100 approaches. Iterate prompts, remember everything used, and just test more and select the approach with, I mean, general prompts without any bias with the less error.
