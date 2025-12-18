import { JobBoardScraper } from "./JobBoardScraper";

type ScraperConstructor = new (...args: any[]) => JobBoardScraper;

class ScraperRegistry {
    private scrapers: Map<string, ScraperConstructor> = new Map();

    register(name: string, scraper: ScraperConstructor): void {
        this.scrapers.set(name.toLowerCase(), scraper);
    }

    get(name: string): ScraperConstructor | undefined {
        return this.scrapers.get(name.toLowerCase());
    }

    has(name: string): boolean {
        return this.scrapers.has(name.toLowerCase());
    }

    getAllScraperNames(): string[] {
        return Array.from(this.scrapers.keys());
    }
}

export const scraperRegistry = new ScraperRegistry();
