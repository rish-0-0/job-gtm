import { scraperRegistry } from "./ScraperRegistry";
import { DiceScraper } from "./DiceScraper";
import { SimplyHiredScraper } from "./SimplyHiredScraper";

scraperRegistry.register("dice", DiceScraper);
scraperRegistry.register("simplyhired", SimplyHiredScraper);

export { ScraperFactory } from "./ScraperFactory";
export { JobBoardScraper, JobListing } from "./JobBoardScraper";
