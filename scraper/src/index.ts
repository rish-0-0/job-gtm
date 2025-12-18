import Fastify, { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { ScraperFactory } from "./scrapers";

const port: number = process.env.PORT ? parseInt(process.env.PORT) : 6000;

const app: FastifyInstance = Fastify({
    logger: true,
    // Disable all timeouts - scraping can take a long time
    connectionTimeout: 0,
    keepAliveTimeout: 0,
    requestTimeout: 0
});

interface ScrapeRequest {
    scraper: string;
    params?: {
        page: number;
        [key: string]: any;
    }
}

app.post<{ Body: ScrapeRequest }>("/scrape", {
    schema: {
        body: {
            type: "object",
            required: ["scraper"],
            properties: {
                scraper: { type: "string" },
                params: { type: "object", additionalProperties: true, properties: {
                    page: { type: "number" }
                }}
            }
        },
        response: {
            200: {
                type: "object",
                properties: {
                    success: { type: "boolean" },
                    scraper: { type: "string" },
                    result: {
                        type: "array",
                        items: {
                            type: "object",
                            properties: {
                                companyTitle: { type: "string" },
                                jobRole: { type: "string" },
                                salaryRange: { type: "string" },
                                minSalary: { type: ["number", "null"] },
                                maxSalary: { type: ["number", "null"] },
                                requiredExperience: { type: "string" },
                                jobLocation: { type: "string" },
                                jobDescription: { type: "string" },
                                datePosted: { type: "string" },
                                postingUrl: { type: "string" },
                                seniorityLevel: { type: "string" },
                                hiringTeam: { type: "string" },
                                aboutCompany: { type: "string" },
                                employmentType: { type: "string" }
                            }
                        }
                    }
                }
            }
        }
    }
}, async (request: FastifyRequest<{ Body: ScrapeRequest }>, reply: FastifyReply) => {
    try {
        const { scraper: scraperName, params = { page: 1 } } = request.body;

        app.log.info({ scraperName, params, requestBody: request.body }, "Scraping started - received params");

        if (!ScraperFactory.isScraperAvailable(scraperName)) {
            return reply.status(400).send({
                error: "Invalid scraper",
                message: `Scraper "${scraperName}" not found`,
                availableScrapers: ScraperFactory.getAvailableScrapers()
            });
        }

        const scraper = ScraperFactory.createScraper(scraperName, params);
        const result = await scraper.scrape(params.page || 1);

        app.log.info({ scraperName }, "Scraping completed successfully");

        return reply.status(200).send({
            success: true,
            scraper: scraperName,
            result
        });
    } catch (error) {
        app.log.error({ error }, "Scraping failed");
        return reply.status(500).send({
            error: "Scraping failed",
            message: error instanceof Error ? error.message : "Unknown error"
        });
    }
});

app.get("/scrapers", async (_request: FastifyRequest, reply: FastifyReply) => {
    return reply.status(200).send({
        scrapers: ScraperFactory.getAvailableScrapers()
    });
});

const start: () => Promise<void> = async () => {
    try {
        await app.listen({ port, host: "0.0.0.0" });
        console.log(`Server is running on port ${port}`);
    } catch (err) {
        app.log.error(err);
        process.exit(1);
    }
};

start();