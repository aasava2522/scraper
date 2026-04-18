CREATE TABLE IF NOT EXISTS properties (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_sequence      TEXT,
    detail_path         TEXT,

    deed_number         TEXT,
    case_number         TEXT,
    court               TEXT,
    office              TEXT,
    phone               TEXT,
    venue               TEXT,
    case_officer        TEXT,
    plaintiff           TEXT,
    defendant           TEXT,

    asset_type          TEXT,
    tambon              TEXT,
    amphoe              TEXT,
    province            TEXT,
    land_area           TEXT,
    rai                 TEXT,
    ngan                TEXT,
    sqwah               TEXT,
    owner_name          TEXT,

    sale_condition      TEXT,
    deposit_amount      TEXT,
    appraisal_expert    TEXT,
    appraisal_officer   TEXT,
    appraisal_dept      TEXT,
    appraisal_committee TEXT,
    published_date      TEXT,
    remarks             TEXT,

    auction_date_1      TEXT,
    auction_status_1    TEXT,
    auction_date_2      TEXT,
    auction_status_2    TEXT,
    auction_date_3      TEXT,
    auction_status_3    TEXT,
    auction_date_4      TEXT,
    auction_status_4    TEXT,
    auction_date_5      TEXT,
    auction_status_5    TEXT,
    auction_date_6      TEXT,
    auction_status_6    TEXT,
    auction_date_7      TEXT,
    auction_status_7    TEXT,
    auction_date_8      TEXT,
    auction_status_8    TEXT,
    image_1             TEXT,
    image_2             TEXT,
    image_3             TEXT,
    scraped_at          TEXT,

    UNIQUE(detail_path)
);

CREATE INDEX IF NOT EXISTS idx_properties_case_number
ON properties(case_number);

CREATE INDEX IF NOT EXISTS idx_properties_deed_number
ON properties(deed_number);

CREATE INDEX IF NOT EXISTS idx_properties_province
ON properties(province);

CREATE INDEX IF NOT EXISTS idx_properties_asset_type
ON properties(asset_type);

CREATE INDEX IF NOT EXISTS idx_properties_published_date
ON properties(published_date);
