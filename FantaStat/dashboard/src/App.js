import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Search, X, Filter, SortAsc, SortDesc, Star, Target, TrendingUp, Users, DollarSign, Loader2, AlertCircle, Wifi, WifiOff, Shield,ShieldHalf, Workflow, Goal } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import ReactMarkdown from 'react-markdown';




// API calls al backend Flask
const API_BASE_URL = 'http://127.0.0.1:5000';

// #region Backend Calls
const fetchHeaderData = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stats-header`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error header:', error);
  }
};

const fetchPlayersData = async ({days}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stats/${days}`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error players:', error);
  }
};

const fetchMarkdownNotes = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/notes`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error notes:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error notes:', error);
  }
};

const fetchTeamColors = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/team-colors`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error team colors:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error team colors:', error);
  }
};

const fetchAuctionData = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auction-teams`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error:', result.error);
      return {teams: [], budget: -1};
    }
  } catch (error) {
    console.error('API Connection Error auction teams:', error);
    return {teams: [], budget: -1};
  }
};

const fetchAuctionHistory = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auction-history`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error auction:', error);
  }
};

const pushBuy = async ({buyer, role, name, price}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/buy/${buyer}/${role}/${name}/${price}`);
    const result = await response.json();

    if (result.success) {
      return result.data;
    } else {
      console.error('API Error:', result.error);
    }
  } catch (error) {
    console.error('API Connection Error buy:', error);
  }
};
// #endregion


// #region Utility
const argsort = (arr1, arr2) => {
  let decor = (v, i) => [v, i];          // set index to value
  let undecor = a => a[1];               // leave only index
  let argsort = arr => arr.map(decor).sort().map(undecor);

  return argsort(arr2).map(i => arr1[i]);
}

const findInAuction = ({teams, history, name}) => {
  if (!history || typeof history !== 'object' || Object.keys(history).length === 0) {
    return false; // During loading, assume player is available
  }

  if (!teams || !teams.teams || teams.teams.length === 0) {
    return false;
  }

  return teams.teams.some(team => {
    if (!history[team] || !history[team]['acquisti']) {
      return false;
    }

    return history[team]['acquisti'].some(player =>
      player['nome'].toLowerCase() === name.toLowerCase()
    );
  });
};
// #endregion


// #region Percentage Bar Component
const PercentageBar = ({ value, maxValue = 100 }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const isPositive = value >= 0;
  const absValue = Math.abs(value);
  const height = Math.min((absValue / maxValue) * 100, 100);

  return (
    <div className="relative">
      <div
        className="w-3 h-6 bg-gray-200 rounded overflow-hidden cursor-pointer"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <div
          className={`w-3 rounded transition-all duration-300 ease-out ${
            isPositive ? 'absolute bottom-0 bg-green-500' : 'bg-red-500'
          }`}
          style={{ height: `${height}%` }}
        />
      </div>

      {showTooltip && (
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2
                      bg-gray-800 text-white text-xs rounded px-2 py-1
                      whitespace-nowrap z-50 pointer-events-none">
          {value > 0 ? '+' : ''}{value.toFixed(1)}%
        </div>
      )}
    </div>
  );
};
// #endregion


// #region Dual Line Chart
const CustomTooltip = ({ active, payload, label }) => {
  const isVisible = active && payload && payload.length;
  return (
    <div className="custom-tooltip" style={{
        visibility: isVisible ? 'visible' : 'hidden',
        backgroundColor: '#fff',
        border: '1px solid #ccc',
        borderRadius: '6px',
        fontSize: '12px',
        margin: '5px'
      }}>
      {isVisible && (
        <>
          <p className="label">{`${label} : ${payload[0].payload.props.name}`}</p>
          <p className="intro">{`Squadra : ${payload[0].payload.props.team}`}</p>
          <p className="desc">{`Prezzo : ${payload[0].payload.leftValue}`}</p>
          <p className="desc">{`Budget Previsto : ${payload[0].payload.rightValue}`}</p>
          <p className="desc">{`Bud.Var% : ${payload[0].payload.props.var}`}</p>
        </>
      )}
    </div>
  );
};

const DualAxisChart = ({ title, ylLabel, yrLabel, xLabel, lColor, rColor, data }) => {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-800 mb-3 text-center">
        {title}
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="x"
            tick={{ fontSize: 12 }}
            stroke="#666"
          />

          {/* Scala Y sinistra */}
          <YAxis
            yAxisId="left"
            orientation="left"
            tick={{ fontSize: 12 }}
            stroke={lColor}
            label={{
              value: ylLabel,
              angle: -90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: '12px' }
            }}
          />

          {/* Scala Y destra */}
          {/*
          <YAxis
            yAxisId="left"
            orientation="left"
            tick={{ fontSize: 12 }}
            stroke={rColor}
            label={{
              value: yrLabel,
              angle: 90,
              position: 'insideLeft',
              style: { textAnchor: 'middle', fontSize: '12px' }
            }}
          /> */}

          <Tooltip content={CustomTooltip}
            // contentStyle={{
            //   backgroundColor: '#fff',
            //   border: '1px solid #ccc',
            //   borderRadius: '6px',
            //   fontSize: '12px'
            // }}
            // formatter={(value, name) => [
            //   typeof value === 'number' ? value.toFixed(1) : value,
            //   name === 'leftValue' ? ylLabel : yrLabel
            // ]}
          />

          <Legend
            wrapperStyle={{ fontSize: '12px' }}
            formatter={(value) => value === 'leftValue' ? ylLabel : yrLabel}
          />

          {/* Linea per scala sinistra */}
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="leftValue"
            stroke={lColor}
            strokeWidth={2}
            dot={{ fill: lColor, strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6 }}
          />

          {/* Linea per scala destra */}
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="rightValue"
            stroke={rColor}
            strokeWidth={2}
            dot={{ fill: rColor, strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
// #endregion


// #region Dashboard Component
const Dashboard = () => {

  // #region States
  const [activeTab, setActiveTab] = useState('home');
  const [activeRole, setActiveRole] = useState('P');
  const [header, setHeader] = useState([]);
  const [players, setPlayers] = useState([]);
  const [markdownNotes, setMarkdownNotes] = useState('');
  const [teamColors, setTeamColors] = useState({});
  const [auction, setAuction] = useState({teams: [], budget: -1});
  const [auctionHist, setAuctionHist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRuolo, setSelectedRuolo] = useState('');
  const [selectedSquadra, setSelectedSquadra] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'QA', direction: 'desc' });
  const [squadraId, setSquadraId] = useState("");
  const [statsDays, setStatsDays] = useState("cur");
  const [prezzo, setPrezzo] = useState("");
  const [queryGiocatoreSearch, setQueryGiocatoreSearch] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const giocatoreSearchId = useRef(null);
  const suggestionRefs = useRef([]);
  // #endregion


  // #region Loading
  // Load data on component mount
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);

      try {
        const [headerData, playersData, notesData, colorsData, auctionData, auctionHistData] = await Promise.all([
          fetchHeaderData(),
          fetchPlayersData({days: statsDays}),
          fetchMarkdownNotes(),
          fetchTeamColors(),
          fetchAuctionData(),
          fetchAuctionHistory()
        ]);

        setHeader(headerData);
        setPlayers(playersData);
        setMarkdownNotes(notesData);
        setTeamColors(colorsData);
        setAuction(auctionData);
        setAuctionHist(auctionHistData);
        setError(null);
      } catch (err) {
        setError('Error loading data');
        console.error('Error loading:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [statsDays]);
  // #endregion


  // #region Query Search Giocatore
  useEffect(() => {
    if (queryGiocatoreSearch.trim() === '') {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    const filtered = players.filter(item =>
      item.Giocatore.toLowerCase().includes(queryGiocatoreSearch.toLowerCase())
    );
    const filteredNames = filtered.map((player) => {
      return player.Giocatore + ' (' + player.Ruolo + ')';
    });

    setSuggestions(filteredNames.slice(0, 15)); // Massimo 15 suggerimenti
    setIsOpen(filteredNames.length > 0);
    setSelectedIndex(-1);
  }, [players, queryGiocatoreSearch, auctionHist, auction]);

  const handleGiocatoreSearchChange = (e) => {
    setQueryGiocatoreSearch(e.target.value);
  };

  const handleSuggestionClick = (suggestion) => {
    setQueryGiocatoreSearch(suggestion);
    setIsOpen(false);
    setSelectedIndex(-1);
    giocatoreSearchId.current?.focus();
  };

  const handleGiocatoreSearch = (e) => {
    if (!isOpen) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0) {
          handleSuggestionClick(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setSelectedIndex(-1);
        break;
      default:
        break;
    }
  };

  const clearInputGiocatoreSearch = () => {
    setQueryGiocatoreSearch('');
    setIsOpen(false);
    giocatoreSearchId.current?.focus();
  };

  // Scroll automatico per i suggerimenti selezionati con tastiera
  useEffect(() => {
    if (selectedIndex >= 0 && suggestionRefs.current[selectedIndex]) {
      suggestionRefs.current[selectedIndex].scrollIntoView({
        behavior: 'smooth',
        block: 'nearest'
      });
    }
  }, [selectedIndex]);
  // #endregion


  // #region Filtri e sorting
  const filteredAndSortedPlayers = useMemo(() => {
    let filtered = players.filter(player => {
      const matchesSearch = player.Giocatore.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesRuolo = !selectedRuolo || player.Ruolo === selectedRuolo;
      const matchesSquadra = !selectedSquadra || player.Squadra === selectedSquadra;
      const matchesAuction = !findInAuction({teams: auction, history: auctionHist, name: player.Giocatore});
      return matchesSearch && matchesRuolo && matchesSquadra && matchesAuction;
    });

    if (sortConfig.key) {
      filtered.sort((a, b) => {
        let aValue = a[sortConfig.key];
        let bValue = b[sortConfig.key];

        // Handle numeric values
        if (typeof aValue === 'string' && !isNaN(parseFloat(aValue)) && !isNaN(parseFloat(bValue))) {
          aValue = parseFloat(aValue);
          bValue = parseFloat(bValue);
        } else if (typeof aValue === 'string' && !isNaN(parseFloat(aValue)) && bValue === '') {
          aValue = parseFloat(aValue);
          bValue = -100000.0;
        } else if (typeof aValue === 'string' && aValue === '' && !isNaN(parseFloat(bValue))) {
          aValue = -100000.0;
          bValue = parseFloat(bValue);
        } else if (typeof aValue === 'string') {
          aValue = aValue.toLowerCase();
          bValue = bValue.toLowerCase();
        }

        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [players, searchTerm, selectedRuolo, selectedSquadra, sortConfig, auction, auctionHist]);
  // #endregion


  // #region ColumnHeader component
  const ColumnHeader = ({ label , sort, colspan }) => {
    if (sort) {
      const handleSort = (key) => {
        setSortConfig(prev => ({
          key,
          direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc'
        }));
      };
      return (
        <th colSpan={colspan} className="border text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 p-2"
            onClick={() => handleSort(label)}>
          <div className="flex items-center space-x-1">
            <span>{label}</span>
            {sortConfig.key === label && (
              sortConfig.direction === 'asc' ? <SortAsc className="w-4 h-4" /> : <SortDesc className="w-4 h-4" />
            )}
          </div>
        </th>
      );
    } else {
      return (
        <th colSpan={colspan} className="border text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 p-2">
          <div className="flex items-center space-x-1">
            <span>{label}</span>
          </div>
        </th>
      );
    }
  };
  // #endregion


  // #region Conditional Formatting
  const getRuoloBadgeColor = (ruolo) => {
    const colors = {
      'P': 'bg-orange-100 text-orange-800',
      'D': 'bg-green-100 text-green-800',
      'C': 'bg-blue-100 text-blue-800',
      'A': 'bg-red-100 text-red-800'
    };
    return colors[ruolo] || 'bg-gray-100 text-gray-800';
  };

  const getRuoloHexColor = (ruolo) => {
    const colors = {
      'P': '#ea761d #ea761d66',
      'D': '#1caf54 #1caf5466',
      'C': '#1E40AF #1E40AF66',
      'A': '#e22727 #e2272766'
    };
    return colors[ruolo] || '#1F2937 #1F293766';
  };

  const getFasciaColor = (fascia) => {
    const colors = {
      'TOP': 'bg-red-500 text-white',
      'SEMI': 'bg-orange-500 text-white',
      'F3': 'bg-yellow-500 text-black',
      'F4': 'bg-green-500 text-white',
      'SCO': 'bg-blue-500 text-white',
      'F5': 'bg-gray-500 text-white'
    };
    return colors[fascia] || 'bg-gray-100 text-gray-800';
  };

  const getFantamediaColor = (voto) => {
    const score = parseFloat(voto);
    if (score >= 8) return 'text-green-600 font-bold';
    if (score >= 7) return 'text-green-600';
    if (score >= 6) return 'text-blue-600';
    if (score >= 5.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getPercentageColor = (percentage) => {
    const score = parseFloat(percentage);
    if (score >= 0.9) return 'text-green-600';
    if (score >= 0.75) return 'text-green-600 font-bold';
    if (score >= 0.6) return 'text-blue-600';
    if (score >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getTeamColor = (squadra) => {
    const colors = teamColors[squadra] || ['#CCCCCC', '#000000'];
    return (
      <span style={{"border-radius": '5px', backgroundColor: colors[0] + '99', color: colors[1]}}>
        {' ' + squadra + ' '}
      </span>
    );
  };

  const getLabelBadges = (labelString) => {
    if (!labelString) return [];

    const labelColors = {
      'Bon': 'bg-green-100 text-green-800',
      'Bug': 'bg-red-100 text-red-800',
      'Hype': 'bg-purple-100 text-purple-800',
      'Esca': 'bg-yellow-100 text-yellow-800',
      'Sco': 'bg-blue-100 text-blue-800',
      'Low': 'bg-gray-100 text-gray-800',
      'Ud': 'bg-indigo-100 text-indigo-800',
      'Mod': 'bg-pink-100 text-pink-800'
    };

    const badges = [];
    labelString.split('|').forEach((label, index) => {
      const colors = labelColors[label.trim()] || 'bg-gray-100 text-gray-800';
      badges.push(<span className={`${colors}`}>{' ' + label.trim() + ' '}</span>);
    });
    return badges;
  };
  // #endregion


  // #region Statistics Table
  const setHeaderColumns = () => {
    const cols = [];
    header.forEach((v, i) => cols.push(<ColumnHeader {...{label: v, sort: true, colspan: 1}} />));
    return <tr>{cols}</tr>;
  };

  const setPlayersRows = (players) => {
    const rows = [];
    var count = 0;
    players.forEach((player, i) => {
      const entries = [];
      header.forEach((key, j) => {
        if (key === "Ruolo") {
          entries.push(
            <td key={count} className="whitespace-nowrap">
              <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getRuoloBadgeColor(player[key])}`}>
                {player[key]}
              </span>
            </td>
          );
          count += 1;
        } else if (key === "Squadra") {
          entries.push(
            <td key={count} className={`whitespace-nowrap`}>
              {getTeamColor(player[key])}
            </td>
          );
          count += 1;
        } else if (key === "MV" || key === "MFV") {
          entries.push(
            <td key={count} className={`whitespace-nowrap ${getFantamediaColor(player[key])}`}>
              {player[key]}
            </td>
          );
          count += 1;
        } else if (key === "Over6" || key === "Over6.5" || key === "WinRate") {
          entries.push(
            <td key={count} className={`whitespace-nowrap ${getPercentageColor(player[key])}`}>
              {player[key]}
            </td>
          );
          count += 1;
        } else if (key === "Label") {
          entries.push(
            <td key={count} className="whitespace-nowrap" >
              {getLabelBadges(player[key])}
            </td>
          );
          count += 1;
        } else if (key === "Notes") {
          entries.push(
            <td key={count} className="word-wrap:break-word" >
              {player[key]}
            </td>
          );
          count += 1;
        } else {
          entries.push(<td key={count} className="whitespace-nowrap">{player[key]}</td>);
          count += 1;
        }
      });
      rows.push(<tr key={count} className="hover:bg-gray-50 hover:font-bold">{entries}</tr>);
      count += 1;
    });
    return rows;
  };
  // #endregion


  // #region Auction Table
  const setAuctionHeaderColumns = () => {
    const cols = [];
    cols.push(<ColumnHeader key={0} {...{label: ''}} />);
    auction.teams.forEach((v, i) => cols.push(<ColumnHeader  key={`${i + 1}`} {...{label: v, sort: false, colspan: 3}} />));
    return <tr>{cols}</tr>;
  };

  const setAuctionRows = (history) => {
    // Add this safety check at the beginning
    if (!history || typeof history !== 'object' || Object.keys(history).length === 0) {
      return [];
    }

    const maxRowsPerRole = {'P': 0, 'D': 0, 'C': 0, 'A': 0};
    auction.teams.forEach((v, i) => {
      // Add safety check for each team
      if (!history[v] || !history[v]['acquisti']) {
        console.warn(`Team ${v} missing data`);
        return; // Skip this team
      }

      const nRowsPerRole = {'P': 0, 'D': 0, 'C': 0, 'A': 0};
      history[v]['acquisti'].forEach((aq, j) => {
        nRowsPerRole[aq['ruolo']] += 1;
      });

      Object.keys(maxRowsPerRole).forEach((k) => {
        if (maxRowsPerRole[k] < nRowsPerRole[k]) {
          maxRowsPerRole[k] = nRowsPerRole[k];
        }
      });
    });

    const rows = [];
    var count = 0;
    Object.keys(maxRowsPerRole).forEach((k) => {
      for (let i = 0; i < maxRowsPerRole[k]; i++) {
        const cols = [];
        cols.push(<td key={count} className={`text-center m-1 ${getRuoloBadgeColor(k)}`}>{k}</td>);
        count += 1;
        auction.teams.forEach((v, j) => {
          let filtered = history[v]['acquisti'].filter(player => {
            const matchesSearch = player.ruolo === k;
            return matchesSearch;
          });

          if (i < filtered.length) {
            cols.push(<td key={count} className="m-3">{filtered[i].nome}</td>);
            count += 1;
            cols.push(<td key={count} className="m-1">{filtered[i].prezzo}</td>);
            count += 1;
            cols.push(<td key={count} className=""><PercentageBar key={`${j + i}`} value={filtered[i].var}/></td>);
            count += 1;
          } else {
            cols.push(<td key={count} className=""></td>);
            count += 1;
            cols.push(<td key={count} className=""></td>);
            count += 1;
            cols.push(<td key={count} className=""></td>);
            count += 1;
          }
        });
        rows.push(<tr key={count}>{cols}</tr>);
        count += 1;
      }

      const cols = [];
      cols.push(<td key={count} className=""></td>);
      count += 1;
      auction.teams.forEach((v, j) => {
        cols.push(<td key={count} className="m-1"></td>);
        count += 1;
        cols.push(<td key={count} className="m-1 font-bold">{auctionHist[v].spesa_per_ruolo[k]}</td>);
        count += 1;
        // cols.push(<td className="m-1">{getPercentageBar({value: Math.round(auctionHist[v].spesa_per_ruolo[k]/auctionHist[v].budget_iniziale*100)})}</td>);
        cols.push(<td key={count} ></td>);
        count += 1;
      });
      rows.push(<tr key={count} className='border-b border-t'>{cols}</tr>);
      count += 1;
    });
    count += 1;

    const cols = [];
    cols.push(<td key={count} className=""><DollarSign/></td>);
    count += 1;
    auction.teams.forEach((v, j) => {
      cols.push(<td key={count} className="m-1"></td>);
      count += 1;
      cols.push(<td key={count} className="m-1">{auctionHist[v].budget_rimasto}</td>);
      count += 1;
      // cols.push(<td className="border-b m-1">{getPercentageBar({value: Math.round(auctionHist[v].budget_rimasto/auctionHist[v].budget_iniziale*100)})}</td>);
      cols.push(<td key={count}></td>);
      count += 1;
    });
    count += 1;
    rows.push(<tr key={count}>{cols}</tr>);

    return rows;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    const giocatoreId = queryGiocatoreSearch;
    console.log(squadraId, giocatoreId, prezzo);
    if (squadraId === "" || giocatoreId === "" || prezzo === "") {
      return;
    } else {
      var giocatore = ["", ""];
      if (typeof giocatoreId === 'string') {
        giocatore = giocatoreId.split('(');
      }
      if (giocatore.length < 2) {
        return;
      }

      giocatore[0] = giocatore[0].replace('(', '').replace(')', '').trim();
      giocatore[1] = giocatore[1].replace('(', '').replace(')', '').trim();
      console.log({squadraId, giocatoreId, prezzo});

      try {
        // Add 'await' here - this was missing!
        const result = await pushBuy({
          buyer: squadraId,
          role: giocatore[1],
          name: giocatore[0],
          price: prezzo
        });

        setAuctionHist(result);
      } catch (error) {
        console.error("Error in pushBuy:", error);
      }
    }
  };
  // #endregion


  // #region Auction Graphs
  const getAuctionTimeSeries = ({history, role}) => {
    const charts = [];
    // const roles = ['A', 'C', 'D', 'P'];
    var index = 0;
    // roles.forEach((role, i) => {
      const purchases = [];
      const timestamps = [];
      Object.keys(history).forEach(team => {
        history[team]['acquisti'].forEach((player, j) => {
          if (player['ruolo'] === role) {
            purchases.push({
              x: -1,
              leftValue: player['prezzo'],
              rightValue: Math.round(player['prezzo']/(1.0 + player['var']/100.0), 1),
              props: {
                team: team,
                name: player['nome'],
                var: player['var']
              }
            })
            timestamps.push(player['timestamp']);
          }
        });
      });

      const data = argsort(purchases, timestamps);
      data.map((entry, i) => entry['x'] = i);

      const colors = getRuoloHexColor(role).split(' ');

      if (purchases.length > 0) {
        charts.push(
          <DualAxisChart
            key={index}
            title={role}
            ylLabel='Prezzo'
            yrLabel='Budget Previsto'
            xLabel='#'
            lColor={colors[0]}
            rColor={colors[1]}
            data={data}
          />
        )
      }
      index += 1;
    // });
    return charts;
  };
  // #endregion


  // #region Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-green-600 animate-spin mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Loading Dashboard</h2>
        </div>
      </div>
    );
  }
  // #endregion


  // #region HTML
  return (
    <div className="min-h-screen bg-gray-50">

      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-full mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <Target className="w-8 h-8 text-green-600" />
              <h1 className="text-2xl font-bold text-gray-900">FantaStat Dashboard</h1>
            </div>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <div className="flex items-center space-x-1">
                {error ? (
                  <>
                    <WifiOff className="w-4 h-4 text-red-500" />
                    <span className="text-red-500">Offline</span>
                  </>
                ) : (
                  <>
                    <Wifi className="w-4 h-4 text-green-500" />
                    <span className="text-green-500">Online</span>
                  </>
                )}
              </div>
              <div className="flex items-center space-x-1">
                <Users className="w-4 h-4" />
                <span>{players.length} giocatori</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b">
        <div className="max-w-full mx-auto px-4">
          <div className="flex space-x-8">
            {[
              { id: 'home', label: 'Home', icon: Star },
              { id: 'statistics', label: 'Statistics', icon: TrendingUp },
              { id: 'charts', label: 'Charts', icon: Filter }
            ].map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center space-x-2 py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-green-500 text-green-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-full mx-auto px-4 py-6">

        {/* Home Tab */}
        {activeTab === 'home' && (
          <div>

            {/* Auction Tracker */}
            <div className="grid grid-cols-1 lg:grid-cols-1 gap-6">
              <div className="bg-white rounded-lg shadow p-6">
                {/* Auction Buy */}
                <form onSubmit={handleSubmit} className="flex gap-2 my-4">
                  <select
                    value={squadraId}
                    onChange={(e) => setSquadraId(e.target.value)}
                    className="border p-1"
                  >
                    <option value="">Squadra</option>
                    {auction.teams.map((t, i) => (
                      <option key={i} value={t}>{t}</option>
                    ))}
                  </select>

                  <div>
                    <input
                      ref={giocatoreSearchId}
                      type="text"
                      value={queryGiocatoreSearch}
                      onChange={handleGiocatoreSearchChange}
                      onKeyDown={handleGiocatoreSearch}
                      placeholder="Cerca..."
                      className="border p-1"
                    />

                    {isOpen && suggestions.length > 0 && (
                      <div className="absolute z-100 mt-1 bg-white border border-gray-200
                                    rounded-lg shadow-lg max-h-60 overflow-auto">
                        {suggestions.map((suggestion, index) => (
                          <div
                            key={index}
                            ref={el => suggestionRefs.current[index] = el}
                            onClick={() => handleSuggestionClick(suggestion)}
                            className={`px-4 py-3 cursor-pointer transition-colors duration-150
                                      ${index === selectedIndex
                                        ? 'bg-blue-50 text-blue-700'
                                        : 'text-gray-700 hover:bg-gray-50'
                                      }
                                      ${index !== suggestions.length - 1 ? 'border-b border-gray-100' : ''}
                                      first:rounded-t-lg last:rounded-b-lg`}
                          >
                            <div className="flex items-center">
                              <Search className="h-4 w-4 text-gray-400 mr-3" />
                              <span className="font-small">{suggestion}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {queryGiocatoreSearch && (
                    <button
                      onClick={clearInputGiocatoreSearch}
                      className="inset-y-0 right-0 pr-3 flex items-center
                              hover:text-gray-600 text-gray-400 transition-colors"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  )}

                  <input
                    type="number"
                    value={prezzo}
                    onChange={(e) => setPrezzo(e.target.value)}
                    placeholder="Prezzo"
                    className="border p-1 w-24"
                  />

                  <button
                    type="submit"
                    className="bg-blue-500 text-white px-3 py-1 rounded"
                  >
                    Compra
                  </button>
                </form>
                {/* Auction Table */}
                <table className="table-auto w-full text-sm">
                  <thead>
                    {setAuctionHeaderColumns()}
                  </thead>
                  <tbody>
                    {setAuctionRows(auctionHist)}
                  </tbody>
                </table>
              </div>
            </div>

            <br></br>

            {/* Navigation Tabs */}
            <nav className="bg-white border-b">
              <div className="max-w-full mx-auto px-4">
                <div className="flex space-x-8">
                  {[
                    { id: 'P', label: 'Portieri', icon: Shield },
                    { id: 'D', label: 'Difensori', icon: ShieldHalf },
                    { id: 'C', label: 'Centrocampisti', icon: Workflow },
                    { id: 'A', label: 'Attaccanti', icon: Goal }
                  ].map(tab => {
                    const Icon = tab.icon;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveRole(tab.id)}
                        className={`flex items-center space-x-2 py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
                          activeRole === tab.id
                            ? 'border-green-500 text-green-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span>{tab.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </nav>

            {/* Auction Graphs */}
            <div className="grid grid-cols-1 xl:grid-cols-1 lg:grid-cols-1 gap-6">
              {activeRole === "P" && (
                <div>{getAuctionTimeSeries({history: auctionHist, role: 'P'})}</div>
              )}
              {activeRole === "D" && (
                <div>{getAuctionTimeSeries({history: auctionHist, role: 'D'})}</div>
              )}
              {activeRole === "C" && (
                <div>{getAuctionTimeSeries({history: auctionHist, role: 'C'})}</div>
              )}
              {activeRole === "A" && (
                <div>{getAuctionTimeSeries({history: auctionHist, role: 'A'})}</div>
              )}
            </div>

            <br></br>

            {/* Notes and Stretegies */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Note e Strategie - ora da backend */}
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">📝 Strategia e Note</h2>
                <div className="prose">
                  <ReactMarkdown>{markdownNotes}</ReactMarkdown>
                </div>
              </div>

              {/* Quick Stats & Tools */}
              <div className="space-y-6">
                {/* Connection Status Alert */}
                {error && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <div className="flex items-center space-x-2">
                      <AlertCircle className="w-5 h-5 text-yellow-600" />
                      <span className="text-yellow-800 text-sm">
                        Backend down.
                      </span>
                    </div>
                  </div>
                )}

                <div className="bg-white rounded-lg shadow p-6">
                  <h2 className="text-xl font-bold text-gray-900 mb-4">Quick Stats</h2>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-green-50 p-4 rounded-lg">
                      <div className="text-green-600 text-sm font-medium">Portieri</div>
                      <div className="text-2xl font-bold text-green-900">
                        {players.filter(p => p.Ruolo === 'P').length}
                      </div>
                    </div>
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-blue-600 text-sm font-medium">Difensori</div>
                      <div className="text-2xl font-bold text-blue-900">
                        {players.filter(p => p.Ruolo === 'D').length}
                      </div>
                    </div>
                    <div className="bg-yellow-50 p-4 rounded-lg">
                      <div className="text-yellow-600 text-sm font-medium">Centrocampisti</div>
                      <div className="text-2xl font-bold text-yellow-900">
                        {players.filter(p => p.Ruolo === 'C').length}
                      </div>
                    </div>
                    <div className="bg-red-50 p-4 rounded-lg">
                      <div className="text-red-600 text-sm font-medium">Attaccanti</div>
                      <div className="text-2xl font-bold text-red-900">
                        {players.filter(p => p.Ruolo === 'A').length}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <h2 className="text-xl font-bold text-gray-900 mb-4">Budget</h2>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded">
                      <span>Budget Totale:</span>
                      <span className="font-bold">{auction.budget} crediti</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-yellow-50 rounded">
                      <span>Spesi:</span>
                      <span className="font-bold text-yellow-700">0 crediti</span>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-green-50 rounded">
                      <span>Rimanenti:</span>
                      <span className="font-bold text-green-700">{auction.budget} crediti</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* Statistics Tab */}
        {activeTab === 'statistics' && (
          <div className="space-y-6">
            {/* Connection Status Alert */}
            {error && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-center space-x-2">
                  <AlertCircle className="w-5 h-5 text-yellow-600" />
                  <span className="text-yellow-800 text-sm">
                    Backend down.
                  </span>
                </div>
              </div>
            )}

            {/* Filtri */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Cerca giocatore..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                  />
                </div>

                <select
                  value={selectedRuolo}
                  onChange={(e) => setSelectedRuolo(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="">Tutti i ruoli</option>
                  <option value="P">Portieri</option>
                  <option value="D">Difensori</option>
                  <option value="C">Centrocampisti</option>
                  <option value="A">Attaccanti</option>
                </select>

                <select
                  value={selectedSquadra}
                  onChange={(e) => setSelectedSquadra(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="">Tutte le squadre</option>
                  {[...new Set(players.map(p => p.Squadra))].sort().map((Squadra, i) => (
                    <option key={i} value={Squadra}>{Squadra}</option>
                  ))}
                </select>

                <select
                  value={statsDays}
                  onChange={(e) => setStatsDays(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="cur">Stagione attuale</option>
                  <option value="prec">Stagione precedente</option>
                  <option value="10">10</option>
                  <option value="20">20</option>
                  <option value="38">38</option>
                </select>

                <div className="text-sm text-gray-600 flex items-center">
                  Risultati: <span className="font-bold ml-1">{filteredAndSortedPlayers.length}</span>
                </div>
              </div>
            </div>

            {/* Tabella Giocatori */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full table-auto">
                  <thead className="bg-gray-50">
                    {setHeaderColumns()}
                  </thead>

                  <tbody className="bg-white divide-y divide-gray-200">
                    {setPlayersRows(filteredAndSortedPlayers)}
                  </tbody>

                </table>
              </div>

              {/* {filteredAndSortedPlayers.length > 50 && (
                <div className="bg-gray-50 text-sm text-gray-600 text-center">
                  50 of {filteredAndSortedPlayers.length}
                </div>
              )} */}
            </div>
          </div>
        )}

        {/* Charts Tab */}
        {activeTab === 'charts' && (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <Filter className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Graphs under developmente</h2>
            <p className="text-gray-600">
              This section will contain useful insights on the players data.
            </p>
          </div>
        )}

      </main>

    </div>
  );
  // #endregion
};
// #endregion


export default Dashboard;