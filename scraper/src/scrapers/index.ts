import { scraperRegistry } from "./ScraperRegistry";
import { DiceScraper } from "./DiceScraper";
import { SimplyHiredScraper } from "./SimplyHiredScraper";
import { ZipRecruiterScraper } from "./ZipRecruiterScraper";

scraperRegistry.register("dice", DiceScraper);
scraperRegistry.register("simplyhired", SimplyHiredScraper);
scraperRegistry.register("ziprecruiter", ZipRecruiterScraper);

export { ScraperFactory } from "./ScraperFactory";
export { JobBoardScraper, JobListing } from "./JobBoardScraper";
