-- Tiny JSON encoder. Encode-only is sufficient for the NDJSON exporter.
-- Public domain. Handles: nil, boolean, number, string, table (array/object).
local _, ns = ...
local json = {}
ns.json = json

local function escape(s)
    return (s:gsub('[\\"%c]', function(c)
        if c == "\\" then return "\\\\"
        elseif c == '"' then return '\\"'
        elseif c == "\n" then return "\\n"
        elseif c == "\r" then return "\\r"
        elseif c == "\t" then return "\\t"
        else return string.format("\\u%04x", c:byte()) end
    end))
end

local encode

local function isArray(t)
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" then return false end
        n = n + 1
    end
    for i = 1, n do
        if t[i] == nil then return false end
    end
    return true, n
end

encode = function(v)
    local tv = type(v)
    if v == nil then return "null"
    elseif tv == "boolean" then return v and "true" or "false"
    elseif tv == "number" then
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        return tostring(v)
    elseif tv == "string" then return '"' .. escape(v) .. '"'
    elseif tv == "table" then
        local arr, n = isArray(v)
        if arr then
            local parts = {}
            for i = 1, n do parts[i] = encode(v[i]) end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, val in pairs(v) do
                parts[#parts + 1] = '"' .. escape(tostring(k)) .. '":' .. encode(val)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return "null"
end

json.encode = encode
