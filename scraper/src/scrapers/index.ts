import { scraperRegistry } from "./ScraperRegistry";
import { DiceScraper } from "./DiceScraper";
import { SimplyHiredScraper } from "./SimplyHiredScraper";
import { ZipRecruiterScraper } from "./ZipRecruiterScraper";

// Detail scraper imports
import { detailScraperRegistry } from "./DetailScraperRegistry";
import { DiceDetailScraper } from "./DiceDetailScraper";
import { SimplyHiredDetailScraper } from "./SimplyHiredDetailScraper";
import { ZipRecruiterDetailScraper } from "./ZipRecruiterDetailScraper";

// Register basic scrapers
scraperRegistry.register("dice", DiceScraper);
scraperRegistry.register("simplyhired", SimplyHiredScraper);

// Register ZipRecruiter for multiple cities
const zipRecruiterCities = [
    "Bengaluru",
    "Mumbai",
    "Delhi",
    "Hyderabad",
    "Pune"
];

zipRecruiterCities.forEach(city => {
    // Create a factory class for each city
    class ZipRecruiterCityScraper extends ZipRecruiterScraper {
        constructor() {
            super(city);
        }
    }

    // Register with city-specific name
    scraperRegistry.register(`ziprecruiter-${city.toLowerCase()}`, ZipRecruiterCityScraper);
});

// Register detail scrapers
detailScraperRegistry.register("dice", DiceDetailScraper);
detailScraperRegistry.register("simplyhired", SimplyHiredDetailScraper);
detailScraperRegistry.register("ziprecruiter", ZipRecruiterDetailScraper);

// Exports
export { ScraperFactory } from "./ScraperFactory";
export { JobBoardScraper, JobListing } from "./JobBoardScraper";
export { DetailScraperFactory } from "./DetailScraperFactory";
export { JobDetailScraper, JobDetails } from "./JobDetailScraper";
