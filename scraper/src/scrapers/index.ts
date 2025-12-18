import { scraperRegistry } from "./ScraperRegistry";
import { IndeedScraper } from "./IndeedScraper";
import { DiceScraper } from "./DiceScraper";

scraperRegistry.register("indeed", IndeedScraper);
scraperRegistry.register("dice", DiceScraper);

export { ScraperFactory } from "./ScraperFactory";
export { JobBoardScraper, JobListing } from "./JobBoardScraper";
