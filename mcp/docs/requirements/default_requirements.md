 -----------
the default smarltead campaign creation flow:

user connects --> mcp greets with required mcp token to start work!!!! before mcp token provided, mcp mustn't response anything else besides "go sign up here: <sign up link>, provide mcp key"

after mcp key is provided mcp tells user the default flow: "let's launch smarltead campaign for the segments you need", but first provide me the keys: apollo to source the data, openai to do ai stuff and smartlead to launch the campsigns baby, and apify to scrape websites" (move apify also to setup not to use our)
until apollo, openai, smarltead and apify keys are not setup user is told to setup keys in the ui <link to setup keys>
he 
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



❯ i asked you to use gpt4omnini everywehre execept here: initial user promopt to apollo first filtrers mapping- this  
first step - for this first step use 20 differrnet approaches to test differnet models-prompts,test even gpt5nano or  
other 5 models if neccrssasry for best quality                                                                        
                                                                                                                      
everywhre else gpt4omnini is enough , dont you think? WRITE ALL TESTS RESUTLS TO FILES TO KEEP EVERY                  
KNOWLEDGE!!!!!!!!                                                                                                     
                                                                                                                      
iterate until done, don't stop until best GENERAL SETUP ACHIEVED, without hardcode and any prioir knowledge , your    
task is building god level mcp finding target companies NVER FINISH UNTIL DONE!!!!!!!!!!!! LOG EVERY3THING IN FIELS  



 estimate the latest plan in plans dir, what it misses? 
                                                                                     
  popular fuckups are not demanding project/offer fromthe user, etc                  
                                                                                     
  it would be transparent adn helpful to provide table with checklist of what's      
  required for automated gathering companies/cotnacts and campaing launch and        
  whixch agent on which step is responsible for that , imagine user will provide     
  document like in cases dir and say "use it", launch everywthing in smarltead, so   
  that you must be able to ask immediately any missed parts if user wants such       
  automated launch without further interacting: for instance, imagine user lost to   
  include smarltead emails accpounts to be used or anythinh else — you must require  
  essential info to process request further and automatically cover all flow. but    
  some users will run pipeline one be one, providing info on each step at a time     
  what also must be covererd? so how it must be implemented? act as god mcp          
  builder,  write yourplan version with timestamp in name         



  ❯ i need to see all agents (modules of mcp via openai is called) in agent chain     
  plan , provide it and think ctiriclly - is the order of ther run is correct and    
  matches the requirmetns in requirments dir , is each of the agent is simple        
  enough to solve his single task? for isntance , i'm curisus wht'a the scope of     
  intent    
            
                                                                                     
Intent analysis agent. So, like, I mean, I suppose it's definitely better to have    
separate intent analysis agent and agent, like, pre-flight agent. So that, like, you 
 know, I want you to list all agents and all, like, tasks solved by them. And one    
agent, one task. For instance, Intent is just, you know, need to understand what     
user wants. If user wants, for example, provide MCP token, then it, like, okay, if   
user wants to change some... By the way, check that API tokens are set only via UI,  
right? So, yeah, for instance, user wants to provide a new MCP token or user wants   
to, and that means that, like, in another account will be run further. So totally    
another intent. Or user wants to tell just change sequence somewhere. And for that   
case, another set of agents must be run asking, like, if user don't specify          
something like intent discovered. Yeah, user wants to change sequence, but I don't   
know which campaign, which, you know, other, or user told, hey, this company is not  
targeted for or simply not targeted since, but you don't know which. Like, what user 
 is talking about, which pipeline, which offer. So, I guess, I guess, a good         
architecture is first facing like frontier, like, like guest, like, guest welcome in 
 person at the restaurant, you see? Like, new request comes, this intent, analyze    
the intent. Then, uh, calling first, I guess, uh pre-flight check for each intent,   
you see? Or you will say it's better to combine uh pre-flight checking with uh       
intent, for instance, like with my example, editing campaign or editing target       
definition or launching a pipeline. So should there agents must better include these 
 pre-flight checks, like, what is essential for them? Maybe it's better, but maybe   
it's too much context for them. And there should be another agents for each specific 
 task agent, also sub like, also like uh guard agent uh knowing what are essential   
inputs for that agent. So how better to, how to better make it? Uh, I mean, we are   
using cheap OpenAI models for low costs, but... Each GPT can be good in case it's    
solving only one task. Decide yourself, think as God, think about state-of-the-art   
approach for the systems we are building. 


❯ update your document with archutecture, then think crtically about plan in plans   
dir that another agent implements now[Image #20] and think critically about existing 
 testing approach in tests dir, update architecture docs if neccessary and MAINLY    
ADD NEW FILE WITH GOD LEVEL IMPLMENENTATION PLAN WITH ALL REQUIREMENTS COVERED, all  
use caes from default_reqeruiemtns.md files and exploration.md files       


❯ write also test approacj plan in another file, so separate: implenmentation plan
  , test plan. for 2 agents to give in work seaprately and one will implement
  missing in the architecure, featurs, cores, wahtever elase. and another will 
  improve testing frameworks to match reality more - need to laser focus on flow   
  descrbibed in default_requiremtns.md (keep other tests of course notto loose     
  anything but make testing system TEST EACH SMALL ASPECT, EACT VARIATIN OF        
  ANYTHING STEP ORDER OR USER EXPRESSIONS OR USER MISSIN SMTH TO MAKE SURE MCP     
  KEEPS PUSSHING "I NEED THIS", "I NEED THAT - THAT IS, BUIDLING FULL DEPTH TESTING  
  FRAMEOWKR TO TEST variations of flow in default_requirements.md starting from      
  the ery beginning of account creation)  to adjust tests to cover all               
  reqruirements by real world testing mcp (via real connection, there is already a   
  framework on python used for that find and estaimeta is it good enough or          
  not?)[Image #23] and real schreenshoting to cover alsp that                        
  1. all links are provided as expected ny mp                                        
  2. all is realy visible in ui, make screenshots!  and the information transparent  
  and coreessponds to pavel's feedback above and his real sessions conversation      
  history!                                                                           
  3. all data is shown proeprly and checksum matches ui - db - mcp messages          
  4. all mcp estimations are shown that were critically usefull for pavel like       
  "what are expected costs for apollo, what are expeceted number of companies by     
  these fitlers' etc                                                                 
  5. also consider pavel_feedback dir remaining system parts not implemented yet     
                                                                                     
  that's task reqruiing deep focus, act as focused god building best mcp             
  ever!!!!!!! do your best , don't stop until recheck everythinh 10 times , act as   
  god, write full-covering plan files as result    


  ❯ also add the testing ensurng itreations are seen in ui and can be clicked!!!!!     
[Image #30]  that's essential . also that's the most recent iteration is selected by 
 default, by also it's possible to slect all iterations (which mustn't need to show  
duplicated companies and show thel atest iteration rsult on each company) so better  
to show ALL itereations selected by default , but check that clicking to the first   
oteration for historcal reasons is also possible,, aslo check that apollo fitlers    
are changed across iterations and also viisable in ui                                
                                                                                     
So actually, the flow is as following. There are only two, another agent made the    
approach for, and you should, like, make it run only for, like, two iterations for a 
 start and then go on. I mean, the first one, initial, then after initial analysis   
by users, agent, opus, then improved prompt, improved Apollo filters, and that's the 
 second iteration, and then this prompt and these Apollo filters use first of scale  
for next, just gathering more pages, more pages. Decide yourself. It is actually     
also in Apollo filters. Max pages filter must be applied and some kind of page       
number, limit offset, something like that. Don't spend credits for already gathered  
campaigns, accounts, companies, and yeah, actually, if user tells to, like, find     
more in Apollo, then this Apollo filter change, so it's another iteration. I mean,   
max page filter change, so also shows this filter and ensure this flow works well,   
and, like, analyze this flow carefully, as this is also part of requirements default 
 that you must follow. That's essential. Ask me any questions if you have concerns. 

  also make that 1 adjustment iteration max as rule in code , so that for speed (and since 1 iteration is enough for        
adjsutemntns from your tests right?) not to waste more time  

 Also, ensure that the pipeline is smart enough not to stop gathering until these   
   100 people are gathered. I mean, ensure also while testing that in UI, filters    
  applied, also people filters are applied, right? So once, once all the, like,    
  the flow is, what is the flow? Apollo provides, describe to yourself the flow.   
  Find architectural leaks here for optimization and not stop gathering until      
  targets is achieved. Targets is 100 target people, up to 3 per company, so about 
   30 target companies, right, or 40. So make it the flow, the pipeline flow,      
  optimize it. I mean, once target campaign is found, the campaign is labeled as   
  target, peoples there must be found, right? And like new pages from Apollo must  
  be obtained. This, like, page number also filter must be shown, filter is        
  applied for each iteration, new page, that means new iteration, you remember? So 
   that the pipeline works always finding new companies from Apollo, scraping      
  websites, analyzing them by GPT, determining targets, extracting people until    
  this KPI, 100 people, up to 3 per company is achieved.   