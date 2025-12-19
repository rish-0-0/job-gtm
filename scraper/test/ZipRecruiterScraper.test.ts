import { describe, it } from "mocha";
import { expect } from "chai";
import { ZipRecruiterScraper } from "../src/scrapers/ZipRecruiterScraper";

describe("ZipRecruiterScraper", () => {
    it("should scrape job listings from ZipRecruiter.in", async function() {
        // Skip in CI environment (GitHub Actions blocks ZipRecruiter requests)
        if (process.env.CI) {
            console.log("\n⏭️  Skipping ZipRecruiter scraper test in CI environment (403 forbidden)\n");
            this.skip();
        }

        // Increase timeout for web scraping (30 seconds)
        this.timeout(30000);

        const scraper = new ZipRecruiterScraper();

        console.log("\n🚀 Starting ZipRecruiter scraper test...");
        console.log("Scraping page 1 from https://www.ziprecruiter.in/jobs/search\n");

        const results = await scraper.scrape(1);

        console.log(`\n✅ Successfully scraped ${results.length} job listings\n`);

        // Verify we got results
        expect(results).to.be.an("array");
        expect(results.length).to.be.greaterThan(0);

        // Print first 3 jobs for inspection
        const jobsToDisplay = Math.min(3, results.length);
        console.log(`Displaying first ${jobsToDisplay} job(s):\n`);

        for (let i = 0; i < jobsToDisplay; i++) {
            const job = results[i]!;
            console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
            console.log(`Job #${i + 1}:`);
            console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
            console.log(`🏢 Company:        ${job.companyTitle || 'N/A'}`);
            console.log(`💼 Role:           ${job.jobRole || 'N/A'}`);
            console.log(`📍 Location:       ${job.jobLocation || 'N/A'}`);
            console.log(`💼 Employment:     ${job.employmentType || 'N/A'}`);
            console.log(`💰 Salary Range:   ${job.salaryRange || 'N/A'}`);
            console.log(`   Min Salary:     ${job.minSalary ? '₹' + job.minSalary.toLocaleString() : 'N/A'}`);
            console.log(`   Max Salary:     ${job.maxSalary ? '₹' + job.maxSalary.toLocaleString() : 'N/A'}`);
            console.log(`⏱️  Experience:     ${job.requiredExperience || 'N/A'}`);
            console.log(`📊 Seniority:      ${job.seniorityLevel || 'N/A'}`);
            console.log(`📅 Posted:         ${job.datePosted || 'N/A'}`);
            console.log(`🔗 URL:            ${job.postingUrl || 'N/A'}`);
            console.log(`📝 Description:    ${job.jobDescription ? job.jobDescription.substring(0, 150) + '...' : 'N/A'}`);
            console.log(`👥 Hiring Team:    ${job.hiringTeam || 'N/A'}`);
            console.log(`🏭 About Company:  ${job.aboutCompany || 'N/A'}`);
            console.log();
        }

        // Verify the structure of the first job
        if (results.length > 0) {
            const firstJob = results[0]!;

            expect(firstJob).to.have.property("companyTitle");
            expect(firstJob).to.have.property("jobRole");
            expect(firstJob).to.have.property("salaryRange");
            expect(firstJob).to.have.property("minSalary");
            expect(firstJob).to.have.property("maxSalary");
            expect(firstJob).to.have.property("requiredExperience");
            expect(firstJob).to.have.property("jobLocation");
            expect(firstJob).to.have.property("jobDescription");
            expect(firstJob).to.have.property("datePosted");
            expect(firstJob).to.have.property("postingUrl");
            expect(firstJob).to.have.property("seniorityLevel");
            expect(firstJob).to.have.property("hiringTeam");
            expect(firstJob).to.have.property("aboutCompany");
            expect(firstJob).to.have.property("employmentType");

            // At minimum, job should have a company name and role
            expect(firstJob.companyTitle).to.be.a("string");
            expect(firstJob.jobRole).to.be.a("string");
            expect(firstJob.postingUrl).to.be.a("string");

            // Verify URL is properly formatted
            if (firstJob.postingUrl) {
                expect(firstJob.postingUrl).to.satisfy((url: string) =>
                    url.startsWith('http://') || url.startsWith('https://'),
                    'URL should start with http:// or https://'
                );
            }

            console.log("✅ All job listing fields verified successfully!");
        }
    });
});
