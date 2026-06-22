import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  const platform = searchParams.get("platform") || "all";
  const sentiment = searchParams.get("sentiment") || "all";
  const category = searchParams.get("category") || "all";
  const dateFrom = searchParams.get("dateFrom");
  const dateTo = searchParams.get("dateTo");
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = parseInt(searchParams.get("limit") || "50", 10);
  const offset = (page - 1) * limit;

  try {
    // ── Build filtered query for reviews list ──
    let query = supabase
      .from("reviews")
      .select("*", { count: "exact" })
      .order("scraped_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (platform !== "all") {
      query = query.eq("platform_name", platform);
    }
    if (sentiment !== "all") {
      query = query.eq("sentiment", sentiment);
    }
    if (category !== "all") {
      query = query.eq("category", category);
    }
    if (dateFrom) {
      query = query.gte("scraped_at", dateFrom);
    }
    if (dateTo) {
      query = query.lte("scraped_at", dateTo + "T23:59:59.999Z");
    }

    const { data: reviews, count, error } = await query;

    if (error) {
      console.error("Supabase query error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // ── KPI Calculations ──
    
    // 1. Bugün Gelen Yorum (Locked strictly to today's date in Turkey local time, ignoring date filters)
    const turkeyDateStr = new Date().toLocaleDateString("en-US", { timeZone: "Europe/Istanbul" });
    const [month, day, year] = turkeyDateStr.split("/");
    const todayStart = new Date(Date.UTC(parseInt(year), parseInt(month) - 1, parseInt(day), 0, 0, 0, 0));
    todayStart.setUTCHours(todayStart.getUTCHours() - 3);
    
    let todayQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true })
      .gte("scraped_at", todayStart.toISOString());
    if (platform !== "all") todayQuery = todayQuery.eq("platform_name", platform);
    if (category !== "all") todayQuery = todayQuery.eq("category", category);
    const { count: todayCount } = await todayQuery;

    // 2. Toplam Yorum (Filtered by active platform/date range/category filters)
    let totalQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true });
    if (platform !== "all") totalQuery = totalQuery.eq("platform_name", platform);
    if (category !== "all") totalQuery = totalQuery.eq("category", category);
    if (dateFrom) totalQuery = totalQuery.gte("scraped_at", dateFrom);
    if (dateTo) totalQuery = totalQuery.lte("scraped_at", dateTo + "T23:59:59.999Z");
    const { count: totalFiltered } = await totalQuery;

    // 3. Negatif Yorum Oranı (Filtered by active filters)
    let negQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true })
      .eq("sentiment", "Negative");
    if (platform !== "all") negQuery = negQuery.eq("platform_name", platform);
    if (category !== "all") negQuery = negQuery.eq("category", category);
    if (dateFrom) negQuery = negQuery.gte("scraped_at", dateFrom);
    if (dateTo) negQuery = negQuery.lte("scraped_at", dateTo + "T23:59:59.999Z");
    const { count: negativeCount } = await negQuery;

    const negativeRatio =
      totalFiltered && totalFiltered > 0
        ? Math.round(((negativeCount || 0) / totalFiltered) * 100)
        : 0;

    // ── Sentiment distribution (for pie chart - filtered by active filters) ──
    let sentimentQuery = supabase.from("reviews").select("sentiment");
    if (platform !== "all") sentimentQuery = sentimentQuery.eq("platform_name", platform);
    if (category !== "all") sentimentQuery = sentimentQuery.eq("category", category);
    if (dateFrom) sentimentQuery = sentimentQuery.gte("scraped_at", dateFrom);
    if (dateTo) sentimentQuery = sentimentQuery.lte("scraped_at", dateTo + "T23:59:59.999Z");
    const { data: sentimentData } = await sentimentQuery;

    const sentimentDist = { Positive: 0, Negative: 0, Neutral: 0 };
    sentimentData?.forEach((r) => {
      const s = r.sentiment as keyof typeof sentimentDist;
      if (sentimentDist[s] !== undefined) sentimentDist[s]++;
    });

    // ── Category distribution (for top category KPI - filtered by active filters) ──
    let catQuery = supabase.from("reviews").select("category");
    if (platform !== "all") catQuery = catQuery.eq("platform_name", platform);
    if (category !== "all") catQuery = catQuery.eq("category", category);
    if (dateFrom) catQuery = catQuery.gte("scraped_at", dateFrom);
    if (dateTo) catQuery = catQuery.lte("scraped_at", dateTo + "T23:59:59.999Z");
    // Only count negative for "most complained category"
    catQuery = catQuery.eq("sentiment", "Negative");
    const { data: catData } = await catQuery;

    const catCounts: Record<string, number> = {};
    catData?.forEach((r) => {
      if (r.category && r.category !== "Genel") {
        catCounts[r.category] = (catCounts[r.category] || 0) + 1;
      }
    });
    const topCategory = Object.entries(catCounts).sort(
      ([, a], [, b]) => b - a
    )[0];

    // ── Daily trend data (filtered by active filters, dynamically ranges) ──
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    let trendStartDate = thirtyDaysAgo.toISOString();
    let trendEndDate = new Date().toISOString();

    if (dateFrom) trendStartDate = new Date(dateFrom).toISOString();
    if (dateTo) trendEndDate = new Date(dateTo + "T23:59:59.999Z").toISOString();

    let trendQuery = supabase
      .from("reviews")
      .select("scraped_at, sentiment")
      .gte("scraped_at", trendStartDate)
      .lte("scraped_at", trendEndDate)
      .order("scraped_at", { ascending: true });
      
    if (platform !== "all") trendQuery = trendQuery.eq("platform_name", platform);
    if (category !== "all") trendQuery = trendQuery.eq("category", category);
    const { data: trendData } = await trendQuery;

    const dailyTrend: Record<
      string,
      { date: string; label: string; total: number; positive: number; negative: number; neutral: number }
    > = {};

    const startD = new Date(trendStartDate);
    const endD = new Date(trendEndDate);
    const diffTime = Math.abs(endD.getTime() - startD.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    // Dynamic grouping mode based on date range
    const groupingMode = diffDays <= 90 ? "day" : (diffDays <= 365 ? "week" : "month");

    const formatLabel = (dateStr: string, mode: string) => {
      const d = new Date(dateStr);
      const months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
      if (mode === "day") {
        return `${d.getDate()} ${months[d.getMonth()]}`;
      } else if (mode === "week") {
        return `${d.getDate()} ${months[d.getMonth()]} Hft`;
      } else {
        return `${months[d.getMonth()]} ${d.getFullYear()}`;
      }
    };

    const getGroupKey = (dateStr: string, mode: string) => {
      const d = new Date(dateStr);
      if (mode === "day") {
        return d.toISOString().split("T")[0]; // YYYY-MM-DD
      } else if (mode === "week") {
        // Monday of the week
        const diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
        const mon = new Date(d.setDate(diff));
        return mon.toISOString().split("T")[0];
      } else {
        // First day of month
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
      }
    };

    // Pre-fill structure to ensure empty periods are shown
    if (groupingMode === "day") {
      for (let i = 0; i <= diffDays; i++) {
        const d = new Date(startD);
        d.setDate(d.getDate() + i);
        const key = getGroupKey(d.toISOString(), "day");
        if (!dailyTrend[key]) {
          dailyTrend[key] = { date: key, label: formatLabel(key, "day"), total: 0, positive: 0, negative: 0, neutral: 0 };
        }
      }
    } else if (groupingMode === "week") {
      for (let i = 0; i <= diffDays + 7; i += 7) {
        const d = new Date(startD);
        d.setDate(d.getDate() + i);
        const key = getGroupKey(d.toISOString(), "week");
        if (!dailyTrend[key]) {
          dailyTrend[key] = { date: key, label: formatLabel(key, "week"), total: 0, positive: 0, negative: 0, neutral: 0 };
        }
      }
    } else {
      for (let i = 0; i <= diffDays + 31; i += 28) {
        const d = new Date(startD);
        d.setDate(d.getDate() + i);
        const key = getGroupKey(d.toISOString(), "month");
        if (!dailyTrend[key]) {
          dailyTrend[key] = { date: key, label: formatLabel(key, "month"), total: 0, positive: 0, negative: 0, neutral: 0 };
        }
      }
    }

    trendData?.forEach((r) => {
      if (!r.scraped_at) return;
      const key = getGroupKey(r.scraped_at, groupingMode);
      if (!dailyTrend[key]) {
        dailyTrend[key] = { date: key, label: formatLabel(key, groupingMode), total: 0, positive: 0, negative: 0, neutral: 0 };
      }
      dailyTrend[key].total++;
      const s = r.sentiment.toLowerCase() as "positive" | "negative" | "neutral";
      if (dailyTrend[key][s] !== undefined) {
        dailyTrend[key][s]++;
      }
    });

    const sortedTrend = Object.values(dailyTrend).sort((a, b) => a.date.localeCompare(b.date));

    return NextResponse.json({
      reviews: reviews || [],
      totalCount: count || 0,
      kpi: {
        todayCount: todayCount || 0,
        totalCount: totalFiltered || 0, // returned to show in Toplam Yorum card
        negativeRatio,
        topCategory: topCategory
          ? { name: topCategory[0], count: topCategory[1] }
          : { name: "-", count: 0 },
      },
      sentimentDistribution: sentimentDist,
      dailyTrend: sortedTrend,
    });
  } catch (err) {
    console.error("API error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

/** PATCH: Mark review as read */
export async function PATCH(request: NextRequest) {
  try {
    const body = await request.json();
    const { id } = body;

    if (!id) {
      return NextResponse.json({ error: "Missing review id" }, { status: 400 });
    }

    const { error } = await supabase
      .from("reviews")
      .update({ is_read: true })
      .eq("id", id);

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("PATCH error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
