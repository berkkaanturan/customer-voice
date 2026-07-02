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
  const search = searchParams.get("search") || "";
  const sortBy = searchParams.get("sortBy") || "scraped_at";
  const sortOrder = searchParams.get("sortOrder") || "desc";
  const skipStats = searchParams.get("skipStats") === "true";

  try {
    // Helper to apply common filters
    const applyFilters = (q: any) => {
      let filtered = q;
      if (platform !== "all") filtered = filtered.eq("platform_name", platform);
      if (category !== "all") filtered = filtered.eq("category", category);
      if (sentiment !== "all") filtered = filtered.eq("sentiment", sentiment);
      if (dateFrom) filtered = filtered.gte("scraped_at", dateFrom);
      if (dateTo) filtered = filtered.lte("scraped_at", dateTo + "T23:59:59.999Z");
      if (search.trim()) {
        filtered = filtered.or(`original_text.ilike.%${search}%,subject.ilike.%${search}%`);
      }
      return filtered;
    };

    // ── Build filtered query for reviews list ──
    let query = supabase
      .from("reviews")
      .select("*", { count: "exact" })
      .range(offset, offset + limit - 1);

    query = applyFilters(query);
    query = query.order(sortBy, { ascending: sortOrder === "asc" });

    const { data: reviews, count, error } = await query;

    if (error) {
      console.error("Supabase query error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    // Map legacy Neutral reviews to Negative for binary consistency
    const mappedReviews = reviews?.map((r: any) => ({
      ...r,
      sentiment: r.sentiment === "Positive" ? "Positive" : "Negative"
    })) || [];

    if (skipStats) {
      return NextResponse.json({
        reviews: mappedReviews,
        totalCount: count || 0,
        kpi: {
          todayCount: 0,
          totalCount: count || 0,
          negativeRatio: 0,
          sentimentScore: 50,
          topCategory: { name: "-", count: 0 },
        },
        sentimentDistribution: { Positive: 0, Negative: 0 },
        categoryDistribution: [],
        smartInsight: { todayNegative: 0, yesterdayNegative: 0, changePercent: 0, topCategory: "-" },
        dailyTrend: [],
      });
    }

    
    // ── KPI Calculations ──

    // 1. Prepare all queries
    
    // Today
    const turkeyDateStr = new Date().toLocaleDateString("en-US", { timeZone: "Europe/Istanbul" });
    const [month, day, year] = turkeyDateStr.split("/");
    const todayStart = new Date(Date.UTC(parseInt(year), parseInt(month) - 1, parseInt(day), 0, 0, 0, 0));
    todayStart.setUTCHours(todayStart.getUTCHours() - 3);
    const todayEnd = new Date(todayStart);
    todayEnd.setDate(todayEnd.getDate() + 1);

    let todayQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true })
      .gte("scraped_at", todayStart.toISOString())
      .lt("scraped_at", todayEnd.toISOString());
    if (platform !== "all") todayQuery = todayQuery.eq("platform_name", platform);
    if (category !== "all") todayQuery = todayQuery.eq("category", category);
    if (sentiment !== "all") todayQuery = todayQuery.eq("sentiment", sentiment);
    if (search.trim()) {
      todayQuery = todayQuery.or(`original_text.ilike.%${search}%,subject.ilike.%${search}%`);
    }

    // All filtered data parallel fetcher
    const fetchAllFilteredFieldsParallel = async (selectStr: string, total: number) => {
      if (total === 0) return [];
      const pageSize = 1000;
      const numPages = Math.ceil(total / pageSize);
      const promises = [];
      for (let pageNum = 0; pageNum < numPages; pageNum++) {
        let q = supabase
          .from("reviews")
          .select(selectStr)
          .range(pageNum * pageSize, (pageNum + 1) * pageSize - 1);
        q = applyFilters(q);
        promises.push(q);
      }
      const results = await Promise.all(promises);
      let allData: any[] = [];
      for (const res of results) {
        if (res.error) {
          console.error("Error in parallel fetch page:", res.error);
          throw res.error;
        }
        if (res.data) {
          allData = allData.concat(res.data);
        }
      }
      return allData;
    };
    const totalFiltered = count || 0;
    const fetchAllPromise = fetchAllFilteredFieldsParallel("category, sentiment, scraped_at", totalFiltered);

    // Last 24h
    const last24hStart = new Date();
    last24hStart.setHours(last24hStart.getHours() - 24);
    let last24hQuery = supabase
      .from("reviews")
      .select("sentiment, category")
      .gte("scraped_at", last24hStart.toISOString());
    if (platform !== "all") last24hQuery = last24hQuery.eq("platform_name", platform);

    // Churn
    const CHURN_KEYWORDS = [
      "iptal", "tüketici hakem heyeti", "avukat", "mahkeme", "taahhüt",
      "cayma", "dava", "savcılık", "btk", "şikayet ettim", "hukuki",
      "ceza", "sözleşme feshi", "ihtarname",
    ];
    const churnOrFilter = CHURN_KEYWORDS.map(kw => `original_text.ilike.%${kw}%`).join(",");
    let churnQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true });
    churnQuery = applyFilters(churnQuery);
    churnQuery = churnQuery.or(churnOrFilter);

    // Trends
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const sixtyDaysAgo = new Date();
    sixtyDaysAgo.setDate(sixtyDaysAgo.getDate() - 60);

    let prevStartDate = sixtyDaysAgo.toISOString();
    let prevEndDate = thirtyDaysAgo.toISOString();

    let current30Promise: any = Promise.resolve({ count: null });
    let current30ChurnPromise: any = Promise.resolve({ count: null });

    if (dateFrom && dateTo) {
      const dFrom = new Date(dateFrom);
      const dTo = new Date(dateTo + "T23:59:59.999Z");
      const durationMs = dTo.getTime() - dFrom.getTime();
      prevStartDate = new Date(dFrom.getTime() - durationMs).toISOString();
      prevEndDate = dFrom.toISOString();
    } else {
      let current30Query = supabase
        .from("reviews")
        .select("id", { count: "exact", head: true })
        .gte("scraped_at", thirtyDaysAgo.toISOString());
      if (platform !== "all") current30Query = current30Query.eq("platform_name", platform);
      current30Promise = current30Query;

      let current30ChurnQuery = supabase
        .from("reviews")
        .select("id", { count: "exact", head: true })
        .gte("scraped_at", thirtyDaysAgo.toISOString())
        .or(churnOrFilter);
      if (platform !== "all") current30ChurnQuery = current30ChurnQuery.eq("platform_name", platform);
      current30ChurnPromise = current30ChurnQuery;
    }

    let prevQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true })
      .gte("scraped_at", prevStartDate)
      .lt("scraped_at", prevEndDate);
    if (platform !== "all") prevQuery = prevQuery.eq("platform_name", platform);

    let prevChurnQuery = supabase
      .from("reviews")
      .select("id", { count: "exact", head: true })
      .gte("scraped_at", prevStartDate)
      .lt("scraped_at", prevEndDate)
      .or(churnOrFilter);
    if (platform !== "all") prevChurnQuery = prevChurnQuery.eq("platform_name", platform);

    // ── Execute all independent queries in parallel ──
    const [
      { count: todayCount },
      allData,
      { data: last24hData, error: last24hError },
      { count: churnCountVal },
      { count: c30 },
      { count: c30Churn },
      { count: prevCountVal },
      { count: prevChurnCountVal }
    ] = await Promise.all([
      todayQuery,
      fetchAllPromise,
      last24hQuery,
      churnQuery,
      current30Promise,
      current30ChurnPromise,
      prevQuery,
      prevChurnQuery
    ]);

    // ── Process Results ──

    // 1. allData metrics
    allData.forEach((r: any) => {
      if (r.sentiment !== "Positive") r.sentiment = "Negative";
    });
    const positiveCount = allData.filter((r: any) => r.sentiment === "Positive").length;
    const negativeCount = totalFiltered - positiveCount;
    const negativeRatio = totalFiltered > 0 ? Math.round((negativeCount / totalFiltered) * 100) : 0;
    const sentimentScore = totalFiltered > 0 ? Math.round((positiveCount / totalFiltered) * 100) : 50;
    const sentimentDist = { Positive: positiveCount, Negative: negativeCount };

    const catDistCounts: Record<string, number> = {};
    allData.forEach((r: any) => {
      if (r.category) {
        catDistCounts[r.category] = (catDistCounts[r.category] || 0) + 1;
      }
    });
    const categoryDistribution = Object.entries(catDistCounts)
      .sort(([, a], [, b]) => b - a)
      .map(([name, count]) => ({ name, count }));
    const topCategory = categoryDistribution[0];

    // 2. last24h metrics
    if (last24hError) console.error("Error querying last 24h data:", last24hError);
    const last24hDataList = last24hData || [];
    const last24hTotal = last24hDataList.length;
    const last24hPositive = last24hDataList.filter((r: any) => r.sentiment === "Positive").length;
    const last24hNegative = last24hTotal - last24hPositive;
    const last24hCatCounts: Record<string, number> = {};
    last24hDataList.forEach((r: any) => {
      if (r.category) last24hCatCounts[r.category] = (last24hCatCounts[r.category] || 0) + 1;
    });
    const last24hSortedCats = Object.entries(last24hCatCounts).sort(([, a], [, b]) => b - a);
    const last24hTopCategory = last24hSortedCats[0] ? last24hSortedCats[0][0] : "-";
    const smartInsight = {
      total: last24hTotal,
      positive: last24hPositive,
      negative: last24hNegative,
      topCategory: last24hTopCategory,
    };

    // 3. Churn metrics
    const churnCount = churnCountVal || 0;
    const churnRatio = totalFiltered > 0 ? Math.round((churnCount / totalFiltered) * 100) : 0;

    // 4. Trend metrics
    let currentCountForTrend = totalFiltered;
    let currentChurnCountForTrend = churnCount;
    if (!dateFrom || !dateTo) {
      currentCountForTrend = c30 || 0;
      currentChurnCountForTrend = c30Churn || 0;
    }
    const prevCount = prevCountVal || 0;
    const prevChurnCount = prevChurnCountVal || 0;

    let trendValue = 0;
    if (prevCount > 0) {
      trendValue = Math.round(((currentCountForTrend - prevCount) / prevCount) * 100);
    } else if (currentCountForTrend > 0) {
      trendValue = 100;
    }
    const trendText = `${trendValue >= 0 ? "+" : ""}${trendValue}%`;
    const trendIsPositive = trendValue >= 0;

    const currentChurnRatioForTrend = currentCountForTrend > 0 ? Math.round((currentChurnCountForTrend / currentCountForTrend) * 100) : 0;
    const prevChurnRatio = prevCount > 0 ? Math.round((prevChurnCount / prevCount) * 100) : 0;
    const churnTrendValue = currentChurnRatioForTrend - prevChurnRatio;
    const churnTrendText = `${churnTrendValue >= 0 ? "+" : ""}${churnTrendValue}%`;
    const churnTrendIsPositive = churnTrendValue <= 0;


    // ── Daily trend data ──
    let trendStartDate = "";
    let trendEndDate = "";

    if (dateFrom) {
      trendStartDate = new Date(dateFrom).toISOString();
    } else if (allData.length > 0) {
      const dates = allData.map((r: any) => new Date(r.scraped_at).getTime());
      trendStartDate = new Date(Math.min(...dates)).toISOString();
    } else {
      trendStartDate = thirtyDaysAgo.toISOString();
    }

    if (dateTo) {
      trendEndDate = new Date(dateTo + "T23:59:59.999Z").toISOString();
    } else if (allData.length > 0) {
      const dates = allData.map((r: any) => new Date(r.scraped_at).getTime());
      trendEndDate = new Date(Math.max(...dates)).toISOString();
    } else {
      trendEndDate = new Date().toISOString();
    }

    const trendData = allData;

    const dailyTrend: Record<
      string,
      { date: string; label: string; total: number; positive: number; negative: number }
    > = {};

    const startD = new Date(trendStartDate);
    const endD = new Date(trendEndDate);
    const diffTime = Math.abs(endD.getTime() - startD.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    const groupingMode = diffDays <= 90 ? "day" : diffDays <= 365 ? "week" : "month";

    const formatLabel = (dateStr: string, mode: string) => {
      const d = new Date(dateStr);
      const months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
      if (mode === "day") return `${d.getDate()} ${months[d.getMonth()]}`;
      if (mode === "week") return `${d.getDate()} ${months[d.getMonth()]} Hft`;
      return `${months[d.getMonth()]} ${d.getFullYear()}`;
    };

    const getGroupKey = (dateStr: string, mode: string) => {
      const d = new Date(dateStr);
      if (mode === "day") return d.toISOString().split("T")[0];
      if (mode === "week") {
        const diff = d.getDate() - d.getDay() + (d.getDay() === 0 ? -6 : 1);
        const mon = new Date(d.setDate(diff));
        return mon.toISOString().split("T")[0];
      }
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    };

    // Pre-fill trend buckets
    const step = groupingMode === "day" ? 1 : groupingMode === "week" ? 7 : 28;
    for (let i = 0; i <= diffDays + step; i += step) {
      const d = new Date(startD);
      d.setDate(d.getDate() + i);
      const key = getGroupKey(d.toISOString(), groupingMode);
      if (!dailyTrend[key]) {
        dailyTrend[key] = { date: key, label: formatLabel(key, groupingMode), total: 0, positive: 0, negative: 0 };
      }
    }

    trendData?.forEach((r: any) => {
      if (!r.scraped_at) return;
      const key = getGroupKey(r.scraped_at, groupingMode);
      if (!dailyTrend[key]) {
        dailyTrend[key] = { date: key, label: formatLabel(key, groupingMode), total: 0, positive: 0, negative: 0 };
      }
      dailyTrend[key].total++;
      const s = r.sentiment?.toLowerCase();
      if (s === "positive") dailyTrend[key].positive++;
      else dailyTrend[key].negative++;
    });

    const sortedTrend = Object.values(dailyTrend).sort((a, b) => a.date.localeCompare(b.date));

    return NextResponse.json({
      reviews: mappedReviews,
      totalCount: count || 0,
      kpi: {
        todayCount: todayCount || 0,
        totalCount: totalFiltered || 0,
        churnRatio,
        sentimentScore,
        topCategory: topCategory
          ? { name: topCategory.name, count: topCategory.count }
          : { name: "-", count: 0 },
        trend: {
          value: trendText,
          label: dateFrom && dateTo ? "önceki döneme göre" : "geçen aya göre",
          isPositive: trendIsPositive
        },
        churnRatioTrend: {
          value: churnTrendText,
          label: dateFrom && dateTo ? "önceki döneme göre" : "geçen aya göre",
          isPositive: churnTrendIsPositive
        }
      },
      sentimentDistribution: sentimentDist,
      categoryDistribution,
      smartInsight,
      dailyTrend: sortedTrend,
    });
  } catch (err) {
    console.error("API error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
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
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
