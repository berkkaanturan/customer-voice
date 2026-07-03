import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(request: NextRequest) {
  try {
    const { data: logs, error } = await supabase
      .from("scraper_logs")
      .select("*")
      .order("started_at", { ascending: false })
      .limit(50);

    if (error) {
      console.error("Supabase query error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ logs: logs || [] });
  } catch (err: any) {
    console.error("API error fetching logs:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
