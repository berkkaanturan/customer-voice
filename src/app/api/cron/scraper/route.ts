import { execSync } from 'child_process';
import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  // Vercel'den gelen authorization header'ı kontrol et
  const authHeader = request.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    console.log('[Cron] Scraper çalıştırılıyor...');
    
    // Scraper script'ini çalıştır
    const output = execSync(
      'cd /home/berk/code/customer-voice/scraper && python main.py',
      { 
        encoding: 'utf-8',
        timeout: 300000, // 5 dakika timeout
      }
    );
    
    console.log('[Cron] Scraper tamamlandı');
    
    return NextResponse.json({ 
      success: true,
      message: 'Scraper başarıyla çalıştırıldı',
      timestamp: new Date().toISOString(),
    });
  } catch (err: any) {
    console.error('[Cron] Scraper error:', err.message);
    return NextResponse.json(
      { 
        error: 'Scraper çalıştırılamadı',
        details: err.message,
      },
      { status: 500 }
    );
  }
}
