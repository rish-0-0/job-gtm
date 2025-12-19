import { JobDetailScraper } from "./JobDetailScraper";

type DetailScraperConstructor = new (...args: any[]) => JobDetailScraper;

class DetailScraperRegistry {
    private scrapers: Map<string, DetailScraperConstructor> = new Map();

    register(name: string, scraper: DetailScraperConstructor): void {
        this.scrapers.set(name.toLowerCase(), scraper);
    }

    get(name: string): DetailScraperConstructor | undefined {
        return this.scrapers.get(name.toLowerCase());
    }

    has(name: string): boolean {
        return this.scrapers.has(name.toLowerCase());
    }

    getAllScraperNames(): string[] {
        return Array.from(this.scrapers.keys());
    }
}

export const detailScraperRegistry = new DetailScraperRegistry();
