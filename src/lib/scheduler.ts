import cron from 'node-cron';
import { execSync } from 'child_process';

export function startScheduler() {
  // Her 6 saatte bir çalış (saat 0, 6, 12, 18)
  cron.schedule('0 */6 * * *', async () => {
    try {
      console.log('[Scheduler] Running scraper at:', new Date().toISOString());
      
      const output = execSync(
        'cd /home/berk/code/customer-voice/scraper && python main.py --cron',
        { 
          encoding: 'utf-8',
          timeout: 300000, // 5 dakika timeout
        }
      );
      
      console.log('[Scheduler] Scraper completed successfully');
    } catch (error: any) {
      console.error('[Scheduler] Error running scraper:', error.message);
    }
  });

  console.log('[Scheduler] Cronjob başlatıldı - 6 saatte bir çalışacak');
}
