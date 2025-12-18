import { describe, it } from "mocha";
import { expect } from "chai";
import { DiceScraper } from "../src/scrapers/DiceScraper";

describe("DiceScraper", () => {
    it("should scrape job listings from Dice.com", async function() {
        // Increase timeout for web scraping (30 seconds)
        this.timeout(30000);

        const scraper = new DiceScraper();

        console.log("\n🚀 Starting Dice scraper test...");
        console.log("Scraping page 1 from https://www.dice.com/jobs?radiusUnit=mi\n");

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
            console.log(`   Min Salary:     ${job.minSalary ? '$' + job.minSalary.toLocaleString() : 'N/A'}`);
            console.log(`   Max Salary:     ${job.maxSalary ? '$' + job.maxSalary.toLocaleString() : 'N/A'}`);
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

            console.log("✅ All job listing fields verified successfully!");
        }
    });
});
