import { scraperRegistry } from "./ScraperRegistry";
import { DiceScraper } from "./DiceScraper";
import { SimplyHiredScraper } from "./SimplyHiredScraper";
import { ZipRecruiterScraper } from "./ZipRecruiterScraper";

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

export { ScraperFactory } from "./ScraperFactory";
export { JobBoardScraper, JobListing } from "./JobBoardScraper";
