import { useState, useCallback, useEffect } from "react"
import { useUser, useClerk, SignIn } from "@clerk/clerk-react"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000/api"

// ── column definitions ────────────────────────────────────────────────────────

const COLS = {
  batting: [
    { key: "player_name",  label: "Player" },
    { key: "year",         label: "Year" },
    { key: "team",         label: "Team" },
    { key: "bats",         label: "B" },
    { key: "games",        label: "G" },
    { key: "at_bats",      label: "AB" },
    { key: "runs",         label: "R" },
    { key: "hits",         label: "H" },
    { key: "doubles",      label: "2B" },
    { key: "triples",      label: "3B" },
    { key: "home_runs",    label: "HR" },
    { key: "rbi",          label: "RBI" },
    { key: "stolen_bases", label: "SB" },
    { key: "walks",        label: "BB" },
    { key: "strikeouts",   label: "SO" },
    { key: "avg",          label: "AVG", fmt: v => v?.toFixed(3) ?? "—" },
    { key: "obp",          label: "OBP", fmt: v => v?.toFixed(3) ?? "—" },
    { key: "slg",          label: "SLG", fmt: v => v?.toFixed(3) ?? "—" },
    { key: "ops",          label: "OPS", fmt: v => v?.toFixed(3) ?? "—" },
  ],
  pitching: [
    { key: "player_name",     label: "Player" },
    { key: "year",            label: "Year" },
    { key: "team",            label: "Team" },
    { key: "throws",          label: "T" },
    { key: "wins",            label: "W" },
    { key: "losses",          label: "L" },
    { key: "games",           label: "G" },
    { key: "games_started",   label: "GS" },
    { key: "complete_games",  label: "CG" },
    { key: "shutouts",        label: "SHO" },
    { key: "saves",           label: "SV" },
    { key: "innings_pitched", label: "IP" },
    { key: "hits_allowed",    label: "H" },
    { key: "walks",           label: "BB" },
    { key: "strikeouts",      label: "SO" },
    { key: "era",             label: "ERA", fmt: v => v?.toFixed(2) ?? "—" },
    { key: "whip",            label: "WHIP", fmt: v => v?.toFixed(3) ?? "—" },
    { key: "k_per_9",         label: "K/9", fmt: v => v?.toFixed(1) ?? "—" },
  ],
  fielding: [
    { key: "player_name",   label: "Player" },
    { key: "year",          label: "Year" },
    { key: "team",          label: "Team" },
    { key: "position",      label: "Pos" },
    { key: "games",         label: "G" },
    { key: "games_started", label: "GS" },
    { key: "putouts",       label: "PO" },
    { key: "assists",       label: "A" },
    { key: "errors",        label: "E" },
    { key: "double_plays",  label: "DP" },
    { key: "fielding_pct",  label: "FLD%", fmt: v => v?.toFixed(3) ?? "—" },
  ],
  mlb_api: [
    { key: "date",       label: "Date" },
    { key: "away_team",  label: "Away" },
    { key: "away_score", label: "R" },
    { key: "away_hits",  label: "H" },
    { key: "home_team",  label: "Home" },
    { key: "home_score", label: "R" },
    { key: "home_hits",  label: "H" },
    { key: "status",     label: "Status" },
  ],
  plays: [
    { key: "half",        label: "" },
    { key: "inning",      label: "Inn" },
    { key: "batter",      label: "Batter" },
    { key: "pitcher",     label: "Pitcher" },
    { key: "event",       label: "Event" },
    { key: "rbi",         label: "RBI" },
    { key: "away_score",  label: "Away" },
    { key: "home_score",  label: "Home" },
    { key: "description", label: "Description" },
  ],
  retro_games: [
    { key: "date",            label: "Date" },
    { key: "away_team",       label: "Away" },
    { key: "away_score",      label: "R" },
    { key: "away_hits",       label: "H" },
    { key: "home_team",       label: "Home" },
    { key: "home_score",      label: "R" },
    { key: "home_hits",       label: "H" },
    { key: "winning_pitcher", label: "WP" },
    { key: "attendance",      label: "Att" },
  ],
  retro_batting: [
    { key: "date",       label: "Date" },
    { key: "team",       label: "Team" },
    { key: "home_away",  label: "H/A" },
    { key: "opponent",   label: "Opp" },
    { key: "away_score", label: "Away R" },
    { key: "home_score", label: "Home R" },
    { key: "ab",         label: "AB" },
    { key: "hits",       label: "H" },
    { key: "doubles",    label: "2B" },
    { key: "triples",    label: "3B" },
    { key: "hr",         label: "HR" },
    { key: "rbi",        label: "RBI" },
    { key: "walks",      label: "BB" },
    { key: "strikeouts", label: "K" },
    { key: "runs",       label: "R" },
  ],
  retro_pitching: [
    { key: "date",         label: "Date" },
    { key: "team",         label: "Team" },
    { key: "home_away",    label: "H/A" },
    { key: "opponent",     label: "Opp" },
    { key: "away_score",   label: "Away R" },
    { key: "home_score",   label: "Home R" },
    { key: "ip",           label: "IP",  fmt: v => v?.toFixed(1) ?? "—" },
    { key: "strikeouts",   label: "K" },
    { key: "walks",        label: "BB" },
    { key: "hits_allowed", label: "H" },
    { key: "runs_allowed", label: "R" },
    { key: "decision",     label: "Dec" },
  ],
  retro_advanced: [
    { key: "date",        label: "Date" },
    { key: "player_name", label: "Player" },
    { key: "team",        label: "Team" },
    { key: "opponent",    label: "Opp" },
    { key: "away_score",  label: "Away R" },
    { key: "home_score",  label: "Home R" },
    { key: "ab",          label: "AB" },
    { key: "hits",        label: "H" },
    { key: "hr",          label: "HR" },
    { key: "rbi",         label: "RBI" },
    { key: "runs",        label: "R" },
    { key: "strikeouts",  label: "K" },
  ],
  retro_pitching_search: [
    { key: "date",                 label: "Date" },
    { key: "winning_pitcher_name", label: "Pitcher" },
    { key: "away_team",            label: "Away" },
    { key: "away_score",           label: "R" },
    { key: "home_team",            label: "Home" },
    { key: "home_score",           label: "R" },
    { key: "hits_allowed",         label: "H" },
    { key: "runs_allowed",         label: "R" },
    { key: "strikeouts",           label: "K" },
    { key: "walks",                label: "BB" },
  ],
  retro_plays: [
    { key: "event_num",    label: "#" },
    { key: "inning",       label: "Inn" },
    { key: "batting_team", label: "Batting" },
    { key: "outs",         label: "Out" },
    { key: "batter",       label: "Batter" },
    { key: "pitcher",      label: "Pitcher" },
    { key: "play_text",    label: "Play" },
    { key: "event_type",   label: "Result" },
    { key: "rbi",          label: "RBI" },
    { key: "runs_scored",  label: "R" },
  ],
}

// ── filter config ─────────────────────────────────────────────────────────────

const FILTER_CONFIG = {
  batting: {
    endpoint: "batting",
    sorts: [
      { v: "year", l: "Season" }, { v: "hr", l: "Home runs" },
      { v: "avg", l: "Batting avg" }, { v: "rbi", l: "RBI" },
      { v: "hits", l: "Hits" }, { v: "sb", l: "Stolen bases" },
      { v: "obp", l: "OBP" }, { v: "slg", l: "SLG" }, { v: "ops", l: "OPS" },
    ],
    sections: [
      { title: "Player & season", fields: [
        { id: "player_name", label: "Player name", type: "text", placeholder: "e.g. Babe Ruth", wide: true },
        { id: "team",        label: "Team",        type: "text", placeholder: "NYA or Yankees" },
        { id: "year_from",   label: "Season from", type: "number", placeholder: "1920" },
        { id: "year_to",     label: "Season to",   type: "number", placeholder: "2024" },
        { id: "bats",        label: "Bats", type: "select",
          options: [{ v: "", l: "Any" }, { v: "L", l: "Left" }, { v: "R", l: "Right" }, { v: "B", l: "Both" }] },
      ]},
      { title: "Counting stats", fields: [
        { id: "min_g",    label: "Min games",  type: "number", placeholder: "100" },
        { id: "min_ab",   label: "Min AB",     type: "number", placeholder: "400" },
        { id: "min_hits", label: "Min hits",   type: "number", placeholder: "150" },
        { id: "min_runs", label: "Min runs",   type: "number", placeholder: "80" },
        { id: "min_hr",   label: "Min HR",     type: "number", placeholder: "20" },
        { id: "max_hr",   label: "Max HR",     type: "number", placeholder: "73" },
        { id: "min_rbi",  label: "Min RBI",    type: "number", placeholder: "80" },
        { id: "min_2b",   label: "Min 2B",     type: "number", placeholder: "30" },
        { id: "min_3b",   label: "Min 3B",     type: "number", placeholder: "5" },
        { id: "min_sb",   label: "Min SB",     type: "number", placeholder: "20" },
        { id: "min_bb",   label: "Min BB",     type: "number", placeholder: "60" },
        { id: "min_so",   label: "Min SO",     type: "number", placeholder: "50" },
        { id: "max_so",   label: "Max SO",     type: "number", placeholder: "200" },
      ]},
      { title: "Rate stats", fields: [
        { id: "min_avg", label: "Min AVG", type: "decimal", placeholder: ".250" },
        { id: "max_avg", label: "Max AVG", type: "decimal", placeholder: ".400" },
        { id: "min_obp", label: "Min OBP", type: "decimal", placeholder: ".330" },
        { id: "min_slg", label: "Min SLG", type: "decimal", placeholder: ".450" },
        { id: "min_ops", label: "Min OPS", type: "decimal", placeholder: ".800" },
      ]},
    ],
  },
  pitching: {
    endpoint: "pitching",
    sorts: [
      { v: "year", l: "Season" }, { v: "era", l: "ERA" },
      { v: "wins", l: "Wins" }, { v: "so", l: "Strikeouts" },
      { v: "sv", l: "Saves" }, { v: "whip", l: "WHIP" }, { v: "k9", l: "K/9" },
    ],
    sections: [
      { title: "Player & season", fields: [
        { id: "player_name", label: "Player name", type: "text", placeholder: "e.g. Roger Clemens", wide: true },
        { id: "team",        label: "Team",        type: "text", placeholder: "NYA or Yankees" },
        { id: "year_from",   label: "Season from", type: "number", placeholder: "1980" },
        { id: "year_to",     label: "Season to",   type: "number", placeholder: "2024" },
        { id: "throws",  label: "Throws", type: "select",
          options: [{ v: "", l: "Any" }, { v: "L", l: "Left" }, { v: "R", l: "Right" }] },
        { id: "starter", label: "Role", type: "select",
          options: [{ v: "", l: "Any" }, { v: "yes", l: "Starters only" }, { v: "no", l: "Relievers only" }] },
      ]},
      { title: "Counting stats", fields: [
        { id: "min_g",       label: "Min games",   type: "number", placeholder: "20" },
        { id: "min_gs",      label: "Min starts",  type: "number", placeholder: "15" },
        { id: "min_wins",    label: "Min wins",    type: "number", placeholder: "10" },
        { id: "max_losses",  label: "Max losses",  type: "number", placeholder: "15" },
        { id: "min_sv",      label: "Min saves",   type: "number", placeholder: "10" },
        { id: "min_so",      label: "Min K",       type: "number", placeholder: "150" },
        { id: "max_bb",      label: "Max BB",      type: "number", placeholder: "80" },
        { id: "min_ip",      label: "Min IP",      type: "number", placeholder: "100" },
        { id: "min_cg",      label: "Min CG",      type: "number", placeholder: "5" },
        { id: "min_sho",     label: "Min SHO",     type: "number", placeholder: "2" },
      ]},
      { title: "Rate stats", fields: [
        { id: "min_era",  label: "Min ERA",  type: "decimal", placeholder: "1.00" },
        { id: "max_era",  label: "Max ERA",  type: "decimal", placeholder: "4.00" },
        { id: "max_whip", label: "Max WHIP", type: "decimal", placeholder: "1.30" },
        { id: "min_k9",   label: "Min K/9",  type: "decimal", placeholder: "8.0" },
      ]},
    ],
  },
  fielding: {
    endpoint: "fielding",
    sorts: [
      { v: "year", l: "Season" }, { v: "games", l: "Games" },
      { v: "errors", l: "Errors" }, { v: "fielding_pct", l: "Fielding %" },
    ],
    sections: [
      { title: "Player & season", fields: [
        { id: "player_name", label: "Player name", type: "text", placeholder: "e.g. Ozzie Smith", wide: true },
        { id: "team",        label: "Team",        type: "text", placeholder: "SLN or Cardinals" },
        { id: "year_from",   label: "Season from", type: "number", placeholder: "1980" },
        { id: "year_to",     label: "Season to",   type: "number", placeholder: "2024" },
        { id: "position", label: "Position", type: "select", options: [
          { v: "", l: "Any position" }, { v: "P", l: "P — Pitcher" },
          { v: "C", l: "C — Catcher" }, { v: "1B", l: "1B" },
          { v: "2B", l: "2B" }, { v: "3B", l: "3B" },
          { v: "SS", l: "SS — Shortstop" }, { v: "LF", l: "LF" },
          { v: "CF", l: "CF" }, { v: "RF", l: "RF" }, { v: "OF", l: "OF — Outfield" },
        ]},
      ]},
      { title: "Fielding stats", fields: [
        { id: "min_g",      label: "Min games",  type: "number", placeholder: "100" },
        { id: "max_errors", label: "Max errors", type: "number", placeholder: "10" },
      ]},
    ],
  },
}

// ── shared results table ──────────────────────────────────────────────────────

function ResultsTable({ rows, mode, onGameClick }) {
  if (!rows?.length) return null
  const cols = COLS[mode] ?? Object.keys(rows[0]).map(k => ({ key: k, label: k }))
  const clickable = (mode === "mlb_api") && onGameClick
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>{cols.map(c => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}
              onClick={clickable ? () => onGameClick(row) : undefined}
              className={clickable ? "clickable-row" : ""}
            >
              {cols.map(c => (
                <td key={c.key}
                  style={c.key === "description" ? { whiteSpace: "normal", maxWidth: 280 } : {}}>
                  {c.fmt ? c.fmt(row[c.key]) : (row[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {clickable && <p className="table-hint">Tap a game to see play-by-play</p>}
    </div>
  )
}

// ── live scores ───────────────────────────────────────────────────────────────

function LiveScores({ onGameClick }) {
  const [games, setGames]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState("")

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`${API}/mlb/live`)
        if (!r.ok) throw new Error("Could not load games")
        setGames(await r.json())
      } catch (e) { setError(e.message) }
      finally { setLoading(false) }
    }
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  if (loading) return <div className="loading-msg">Loading today's games…</div>
  if (error)   return <div className="error-msg">{error}</div>
  if (!games.length) return (
    <div className="empty-state">
      <span className="empty-icon">🌙</span>
      <p>No games scheduled today</p>
    </div>
  )

  return (
    <div className="live-section">
      <div className="live-header"><span className="live-dot" />Today's games — refreshes every 30s</div>
      <div className="scorecards">
        {games.map(g => (
          <div key={g.game_pk}
            className={`scorecard ${g.inning ? "sc-live" : g.status === "Final" ? "sc-final" : "sc-upcoming"}`}
            onClick={() => onGameClick(g)}
          >
            <div className="sc-status">{g.inning ? `${g.inning_half} ${g.inning}` : g.status}</div>
            <div className="sc-row"><span className="sc-team">{g.away_team}</span><span className="sc-score">{g.away_score ?? "—"}</span></div>
            <div className="sc-row"><span className="sc-team">{g.home_team}</span><span className="sc-score">{g.home_score ?? "—"}</span></div>
            <div className="sc-venue">{g.venue}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── play by play ──────────────────────────────────────────────────────────────

function PlayByPlay({ game, onBack }) {
  const [plays, setPlays]     = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState("")
  const [inning, setInning]   = useState("")
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    setLoading(true); setError("")
    try {
      const p = new URLSearchParams()
      if (filter) p.set("filter", filter)
      if (inning) p.set("inning", inning)
      const r = await fetch(`${API}/mlb/game/${game.game_pk}/plays?${p}`)
      if (!r.ok) throw new Error("Could not load plays")
      setPlays((await r.json()).plays)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [game.game_pk, filter, inning])

  useEffect(() => { load() }, [load])

  return (
    <div className="pbp-panel">
      <div className="pbp-header">
        <button className="btn-ghost small" onClick={onBack}>← Back</button>
        <div className="pbp-title">
          {game.away_team} {game.away_score ?? ""} @ {game.home_team} {game.home_score ?? ""}
          {game.date ? ` — ${game.date}` : ""}
        </div>
      </div>
      <div className="pbp-filters">
        <select value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="">All plays</option>
          {["hits","hr","runs","so","walks","errors"].map(f =>
            <option key={f} value={f}>{f.toUpperCase()}</option>)}
        </select>
        <select value={inning} onChange={e => setInning(e.target.value)}>
          <option value="">All innings</option>
          {Array.from({ length: 12 }, (_, i) => i + 1).map(i =>
            <option key={i} value={i}>Inning {i}</option>)}
        </select>
      </div>
      {loading && <div className="loading-msg">Loading plays…</div>}
      {error   && <div className="error-msg">{error}</div>}
      {!loading && <ResultsTable rows={plays} mode="plays" />}
      {!loading && !plays.length && <div className="empty-state"><p>No plays match this filter</p></div>}
    </div>
  )
}

// ── AI search ─────────────────────────────────────────────────────────────────

function AiSearch({ onResults, onGameClick }) {
  const [q, setQ]             = useState("")
  const [loading, setLoading] = useState(false)
  const [explanation, setExplanation] = useState("")
  const [sql, setSql]         = useState("")
  const [showSql, setShowSql] = useState(false)
  const [source, setSource]   = useState("")
  const [error, setError]     = useState("")

  const examples = [
    "Most home runs in a single season, all time",
    "No-hitters since 2000",
    "Babe Ruth game log 1927",
    "Complete game shutouts with 10+ strikeouts",
    "Hall of Famers born outside the United States",
    "Aaron Judge games with 2+ HR in 2022",
  ]

  const run = useCallback(async (queryText) => {
    const text = queryText || q
    if (!text.trim()) return
    setLoading(true)
    setError(""); setSql(""); setExplanation(""); setSource("")
    try {
      const res = await fetch(`${API}/ai-search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || "Search failed")
      const data = await res.json()
      setExplanation(data.explanation)
      setSql(data.sql || "")
      setSource(data.source)
      const mode = data.source === "mlb_api" ? "mlb_api"
             : data.source === "lahman"   ? "batting"
             : data.action  === "search_games"    ? "retro_games"
             : data.action  === "player_gamelog"  ? "retro_batting"
             : data.action  === "player_pitching" ? "retro_pitching"
             : data.action  === "advanced_search" ? (
                 (data.params?.shutout || data.params?.no_hitter || data.params?.min_k_game)
                 ? "retro_pitching_search" : "retro_advanced"
               )
             : data.action  === "game_plays"      ? "retro_plays"
             : "batting"
      onResults(data.results, mode)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [q, onResults])

  return (
    <div className="ai-panel">
      <div className="ai-header">
        <span className="ai-badge">AI</span>
        <span>Ask anything — career stats, game results, live scores</span>
      </div>
      <div className="ai-input-row">
        <input
          className="ai-input"
          placeholder="e.g. most strikeouts in a season since 2000…"
          value={q}
          onChange={e => setQ(e.target.value)}
          onKeyDown={e => e.key === "Enter" && run()}
          disabled={loading}
        />
        <button className="btn-primary" onClick={() => run()} disabled={loading || !q.trim()}>
          {loading ? <span className="spinner" /> : "Search"}
        </button>
      </div>
      <div className="examples-list">
        <span className="examples-label">Try asking</span>
        {examples.map(s => (
          <button key={s} className="example-link" onClick={() => { setQ(s); run(s) }}>{s}</button>
        ))}
      </div>
      {error && <div className="error-msg">{error}</div>}
      {explanation && (
        <div className="ai-explanation">
          <span className={`source-badge src-${source}`}>
            {source === "mlb_api" ? "MLB API"
           : source === "retrosheet" ? "Retrosheet"
           : "Lahman DB"}
          </span>
          <span>{explanation}</span>
          {sql && <button className="link-btn" onClick={() => setShowSql(v => !v)}>
            {showSql ? "Hide SQL" : "Show SQL"}
          </button>}
        </div>
      )}
      {showSql && sql && <pre className="sql-block">{sql}</pre>}
    </div>
  )
}

// ── filter search ─────────────────────────────────────────────────────────────

function FilterSearch({ onResults }) {
  const [mode, setMode]       = useState("batting")
  const [values, setValues]   = useState({})
  const [sortBy, setSortBy]   = useState("year")
  const [sortDir, setSortDir] = useState("desc")
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState("")

  const cfg = FILTER_CONFIG[mode]

  const set = k => e => setValues(v => ({ ...v, [k]: e.target.value }))

  const switchMode = m => { setMode(m); setValues({}) }

  const run = async () => {
    setLoading(true); setError("")
    try {
      const params = new URLSearchParams()
      Object.entries(values).forEach(([k, v]) => { if (v) params.set(k, v) })
      params.set("sort_by", sortBy)
      params.set("sort_dir", sortDir)
      const res = await fetch(`${API}/search/${cfg.endpoint}?${params}`)
      if (!res.ok) throw new Error((await res.json()).detail || "Search failed")
      onResults(await res.json(), mode)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="filter-panel">
      {/* stat type tabs */}
      <div className="stat-tabs">
        {["batting", "pitching", "fielding"].map(m => (
          <button key={m} className={`stat-tab ${mode === m ? "active" : ""}`} onClick={() => switchMode(m)}>
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>

      <div className="filter-body">
        {cfg.sections.map(sec => (
          <div key={sec.title} className="filter-section">
            <div className="section-head">
              <span className="section-diamond" />
              <span className="section-title">{sec.title}</span>
            </div>
            <div className="filter-row">
              {sec.fields.map(f => (
                <div key={f.id} className={`ff ${f.wide ? "ff-wide" : ""}`}>
                  <label htmlFor={f.id}>{f.label}</label>
                  {f.type === "select" ? (
                    <select id={f.id} value={values[f.id] || ""} onChange={set(f.id)}>
                      {f.options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
                    </select>
                  ) : (
                    <input
                      id={f.id}
                      type={f.type === "decimal" ? "number" : f.type === "number" ? "number" : "text"}
                      step={f.type === "decimal" ? "0.001" : undefined}
                      inputMode={f.type === "number" || f.type === "decimal" ? "decimal" : "text"}
                      placeholder={f.placeholder}
                      value={values[f.id] || ""}
                      onChange={set(f.id)}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && <div className="error-msg" style={{ margin: "0 18px" }}>{error}</div>}

      <div className="filter-actions">
        <div className="sort-row">
          <label>Sort</label>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
            {cfg.sorts.map(s => <option key={s.v} value={s.v}>{s.l}</option>)}
          </select>
          <select value={sortDir} onChange={e => setSortDir(e.target.value)}>
            <option value="desc">High → Low</option>
            <option value="asc">Low → High</option>
          </select>
        </div>
        <div className="filter-actions-right">
          <button className="btn-ghost" onClick={() => setValues({})}>Clear</button>
          <button className="btn-primary" onClick={run} disabled={loading}>
            {loading ? <span className="spinner" /> : "Search"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── app shell ─────────────────────────────────────────────────────────────────

function AppInner() {
  const [tab, setTab]           = useState("ai")
  const [results, setResults]   = useState([])
  const [resultMode, setResultMode] = useState("batting")
  const [selectedGame, setSelectedGame] = useState(null)

  const handleResults = (data, mode) => {
    setResults(data); setResultMode(mode); setSelectedGame(null)
    // scroll results into view on mobile
    setTimeout(() => document.getElementById("results-anchor")?.scrollIntoView({ behavior: "smooth" }), 100)
  }

  return (
    <main className="main">
      <div className="search-toggle">
        {[["ai", "AI"], ["filter", "Filter"], ["live", "⚡ Live"]].map(([id, label]) => (
          <button key={id}
            className={`toggle-btn ${tab === id ? "active" : ""} ${id === "live" ? "live-tab" : ""}`}
            onClick={() => { setTab(id); setSelectedGame(null) }}
          >{label}</button>
        ))}
      </div>

      {selectedGame ? (
        <PlayByPlay game={selectedGame} onBack={() => setSelectedGame(null)} />
      ) : (
        <>
          {tab === "ai"     && <AiSearch onResults={handleResults} onGameClick={setSelectedGame} />}
          {tab === "filter" && <FilterSearch onResults={handleResults} />}
          {tab === "live"   && <LiveScores onGameClick={setSelectedGame} />}

          <div id="results-anchor" />

          {tab !== "live" && results.length > 0 && (
            <div className="results-section">
              <div className="results-header">
                {results.length} result{results.length !== 1 ? "s" : ""}
                {resultMode === "mlb_api" && <span className="results-hint"> — tap a game for play-by-play</span>}
              </div>
              <ResultsTable rows={results} mode={resultMode}
                onGameClick={resultMode === "mlb_api" ? setSelectedGame : null} />
            </div>
          )}

          {tab !== "live" && results.length === 0 && (
            <div className="empty-state">
              <span className="empty-icon">⚾</span>
              <p>Search above to explore stats from 1871 to today</p>
            </div>
          )}
        </>
      )}
    </main>
  )
}

// ── auth gate ─────────────────────────────────────────────────────────────────

function SignInScreen() {
  return (
    <div className="auth-gate">
      <div className="auth-card">
        <div className="logo" style={{ justifyContent: "center", marginBottom: 4 }}>
          <span className="logo-diamond">◆</span>
          <span className="logo-text">Diamond Stats</span>
        </div>
        <p className="auth-subtitle">Sign in to access 150 years of baseball history</p>
        <SignIn routing="hash" afterSignInUrl="/" />
      </div>
    </div>
  )
}

export default function Root() {
  const { isSignedIn, isLoaded } = useUser()
  const { signOut, user } = useClerk()

  if (!isLoaded) return <div className="auth-gate"><div className="loading-msg">Loading…</div></div>
  if (!isSignedIn) return <SignInScreen />

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div>
            <div className="logo">
              <span className="logo-diamond">◆</span>
              <span className="logo-text">Diamond Stats</span>
            </div>
            <p className="tagline">150 years of baseball · Live scores · Play-by-play</p>
          </div>
          <div className="user-menu">
            <span className="user-email">{user?.primaryEmailAddress?.emailAddress}</span>
            <button className="btn-signout" onClick={() => signOut()}>Sign out</button>
          </div>
        </div>
      </header>
      <AppInner />
      <footer className="footer">
        ⚾ Diamond Stats — Built with love for baseball nerds everywhere
        <br />
        Play-by-play data courtesy of{" "}
        <a href="https://www.retrosheet.org" target="_blank" rel="noreferrer">Retrosheet</a>.
        {" "}The information used here was obtained free of charge from and is copyrighted by Retrosheet.
        <br />
        Season stats from the{" "}
        <a href="https://www.seanlahman.com" target="_blank" rel="noreferrer">Lahman Baseball Database</a>.
      </footer>
    </div>
  )
}
