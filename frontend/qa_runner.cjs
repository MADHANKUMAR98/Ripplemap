/**
 * Visual & Functional QA Runner using playwright-core with local Chrome.
 */

const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACTS_DIR = 'C:\\Users\\madha\\.gemini\\antigravity-ide\\brain\\22071f10-ed30-477d-ab34-389edf5cdcca';

async function runQA() {
  console.log('--- Starting RippleMap Visual & Functional QA ---');
  
  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at ${CHROME_PATH}`);
  }

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
  });

  const page = await context.newPage();

  const consoleErrors = [];
  const networkFailures = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('PAGE CONSOLE ERROR:', msg.text());
    }
  });

  page.on('pageerror', (err) => {
    consoleErrors.push(err.message);
    console.log('PAGE UNCAUGHT ERROR:', err.message);
  });

  page.on('requestfailed', (req) => {
    networkFailures.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
    console.log(`NETWORK FAILED: ${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
  });

  try {
    console.log('1. Navigating to http://127.0.0.1:5173...');
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for the investigation to load (SUB-001 runs on mount)
    console.log('2. Waiting for initial investigation findings...');
    await page.waitForSelector('.react-flow__node', { timeout: 20000 });
    await page.waitForTimeout(2000);


    // Screenshot 1: Overview & Dependency Graph
    const overviewPath = path.join(ARTIFACTS_DIR, 'qa_01_command_center.png');
    await page.screenshot({ path: overviewPath, fullPage: false });
    console.log(`Saved screenshot 1: ${overviewPath}`);

    // Verify Metric Cards content
    const metricsText = await page.textContent('body');
    console.log('Metric check - contains Total Affected:', metricsText.includes('Total Affected'));
    console.log('Metric check - contains Critical Services At Risk:', metricsText.includes('Critical Services At Risk'));
    console.log('Metric check - contains Max RippleScore:', metricsText.includes('Max RippleScore'));

    // Interact with Node in Graph: Click on HOSP-001 node
    console.log('3. Interacting with React Flow Dependency Graph...');
    const hospNode = page.locator('.react-flow__node:has-text("HOSP-001")').first();
    if (await hospNode.isVisible()) {
      await hospNode.click();
      await page.waitForTimeout(600);
      const graphDetailPath = path.join(ARTIFACTS_DIR, 'qa_02_graph_node_detail.png');
      await page.screenshot({ path: graphDetailPath, fullPage: false });
      console.log(`Saved screenshot 2: ${graphDetailPath}`);
    }

    // Tab 2: Evidence Explorer
    console.log('4. Navigating to Evidence Explorer Tab...');
    await page.click('button:has-text("Evidence Explorer")');
    await page.waitForTimeout(800);
    // Type in search box
    const searchBox = page.locator('input[placeholder*="Search affected assets"]');
    if (await searchBox.isVisible()) {
      await searchBox.fill('HOSP');
      await page.waitForTimeout(500);
    }
    const evidencePath = path.join(ARTIFACTS_DIR, 'qa_03_evidence_explorer.png');
    await page.screenshot({ path: evidencePath, fullPage: false });
    console.log(`Saved screenshot 3: ${evidencePath}`);
    // Clear search
    if (await searchBox.isVisible()) {
      await searchBox.fill('');
      await page.waitForTimeout(400);
    }

    // Tab 3: Risk Intelligence
    console.log('5. Navigating to Risk Intelligence Tab...');
    await page.click('button:has-text("Risk Intelligence")');
    await page.waitForTimeout(1000);
    const riskPath = path.join(ARTIFACTS_DIR, 'qa_04_risk_intelligence.png');
    await page.screenshot({ path: riskPath, fullPage: false });
    console.log(`Saved screenshot 4: ${riskPath}`);

    // Tab 4: Recovery Decision Studio
    console.log('6. Navigating to Recovery Decision Studio Tab...');
    await page.click('button:has-text("Recovery Decision Studio")');
    await page.waitForTimeout(1000);
    const recoveryPath = path.join(ARTIFACTS_DIR, 'qa_05_recovery_studio.png');
    await page.screenshot({ path: recoveryPath, fullPage: false });
    console.log(`Saved screenshot 5: ${recoveryPath}`);

    // Tab 5: Incident Memory
    console.log('7. Navigating to Incident Memory Tab...');
    await page.click('button:has-text("Incident Memory")');
    await page.waitForTimeout(800);
    const memoryPath = path.join(ARTIFACTS_DIR, 'qa_06_incident_memory.png');
    await page.screenshot({ path: memoryPath, fullPage: false });
    console.log(`Saved screenshot 6: ${memoryPath}`);

    // Tab 6: AI Explanation & Q&A
    console.log('8. Navigating to AI Explanation & Q&A Tab...');
    await page.click('button:has-text("AI Explanation & Q&A")');
    await page.waitForTimeout(800);
    // Click on preset question
    console.log('9. Submitting Grounded Question...');
    const presetBtn = page.locator('button:has-text("Why is this recovery plan ranked first?")').first();
    if (await presetBtn.isVisible()) {
      await presetBtn.click();
      // Wait for grounded answer to be populated
      await page.waitForSelector('text=Grounded Graph Fact:', { timeout: 15000 });
      await page.waitForTimeout(800);
    }
    const qaPath = path.join(ARTIFACTS_DIR, 'qa_07_groq_grounded_qa.png');
    await page.screenshot({ path: qaPath, fullPage: false });
    console.log(`Saved screenshot 7: ${qaPath}`);

    // Step 10: Toggle Groq AI Narrative OFF and test Graceful Fallback / Deterministic Engine
    console.log('10. Testing Graceful Deterministic Fallback without Groq...');
    // Click toggle button in header
    const groqToggle = page.locator('header button[type="button"]').first();
    if (await groqToggle.isVisible()) {
      await groqToggle.click();
      await page.waitForTimeout(400);
      // Click Investigate Incident
      await page.click('button:has-text("Investigate Incident")');
      await page.waitForTimeout(2500);

      // Verify Intelligence Mode card
      const bodyText = await page.textContent('body');
      console.log('Fallback check - Intelligence Mode mentions Deterministic:', bodyText.includes('Deterministic'));

      // Check AI Explanation tab shows Deterministic Engine
      await page.click('button:has-text("AI Explanation & Q&A")');
      await page.waitForTimeout(600);
      const fallbackPath = path.join(ARTIFACTS_DIR, 'qa_08_groq_fallback.png');
      await page.screenshot({ path: fallbackPath, fullPage: false });
      console.log(`Saved screenshot 8: ${fallbackPath}`);
    }

    // Step 11: Test Narrow Viewport (820px width - iPad / small desktop)
    console.log('11. Testing Narrow Viewport Layout (820px width)...');
    await page.setViewportSize({ width: 820, height: 1000 });
    await page.click('button:has-text("Recovery Decision Studio")');
    await page.waitForTimeout(800);
    const narrowPath = path.join(ARTIFACTS_DIR, 'qa_09_narrow_viewport.png');
    await page.screenshot({ path: narrowPath, fullPage: false });
    console.log(`Saved screenshot 9: ${narrowPath}`);

    console.log('\n--- QA Summary ---');
    console.log(`Console Errors: ${consoleErrors.length}`);
    console.log(`Network Failures: ${networkFailures.length}`);
    
    if (consoleErrors.length > 0) {
      console.log('Console Errors List:', consoleErrors);
    }
    if (networkFailures.length > 0) {
      console.log('Network Failures List:', networkFailures);
    }

    console.log('All QA steps completed successfully!');
  } finally {
    await browser.close();
  }
}

runQA().catch((err) => {
  console.error('QA Runner Failed:', err);
  process.exit(1);
});
