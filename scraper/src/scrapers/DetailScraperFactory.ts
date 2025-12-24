import { JobDetailScraper } from "./JobDetailScraper";
import { detailScraperRegistry } from "./DetailScraperRegistry";

export class DetailScraperFactory {
    static createScraper(scraperName: string, ...args: any[]): JobDetailScraper {
        const ScraperClass = detailScraperRegistry.get(scraperName);

        if (!ScraperClass) {
            throw new Error(
                `Detail scraper "${scraperName}" not found. Available scrapers: ${detailScraperRegistry.getAllScraperNames().join(", ")}`
            );
        }

        return new ScraperClass(...args);
    }

    static isScraperAvailable(scraperName: string): boolean {
        return detailScraperRegistry.has(scraperName);
    }

    static getAvailableScrapers(): string[] {
        return detailScraperRegistry.getAllScraperNames();
    }

    /**
     * Detect which scraper to use based on URL
     */
    static detectScraperFromUrl(url: string): string | null {
        const urlLower = url.toLowerCase();

        if (urlLower.includes('dice.com')) {
            return 'dice';
        }
        if (urlLower.includes('simplyhired.co.in')) {
            return 'simplyhired';
        }
        if (urlLower.includes('ziprecruiter.in')) {
            return 'ziprecruiter';
        }

        return null;
    }
}
