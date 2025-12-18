import { JobBoardScraper } from "./JobBoardScraper";
import { scraperRegistry } from "./ScraperRegistry";

export class ScraperFactory {
    static createScraper(scraperName: string, ...args: any[]): JobBoardScraper {
        const ScraperClass = scraperRegistry.get(scraperName);

        if (!ScraperClass) {
            throw new Error(`Scraper "${scraperName}" not found. Available scrapers: ${scraperRegistry.getAllScraperNames().join(", ")}`);
        }

        return new ScraperClass(...args);
    }

    static isScraperAvailable(scraperName: string): boolean {
        return scraperRegistry.has(scraperName);
    }

    static getAvailableScrapers(): string[] {
        return scraperRegistry.getAllScraperNames();
    }
}
