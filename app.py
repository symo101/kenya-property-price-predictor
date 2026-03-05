import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_squared_error

#Page config
st.set_page_config(
    page_title="Kenya Property Price Predictor",
    page_icon="🏠",
    layout="wide"
)

#Custom CSS
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #1565C0;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #1565C0;
    }
    .metric-label {
        font-size: 13px;
        color: #666;
        margin-top: 4px;
    }
    .prediction-box {
        background: linear-gradient(135deg, #1565C0, #1976D2);
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        color: white;
        box-shadow: 0 4px 15px rgba(21,101,192,0.3);
    }
    .prediction-price {
        font-size: 42px;
        font-weight: bold;
        margin: 10px 0;
    }
    .stSelectbox label, .stSlider label { font-weight: 600; }
</style>
""", unsafe_allow_html=True)


#Load & Train (cached so it only runs once)
@st.cache_data
def load_and_train():
    df = pd.read_csv('buyrentkenya_clean.csv')
    df = df.replace('', np.nan)

    le = LabelEncoder()
    df['property_type_encoded'] = le.fit_transform(df['property_type'])

    features = ['bedrooms', 'bathrooms', 'is_sale', 'is_nairobi',
                'total_rooms', 'property_type_encoded']
    target   = 'price_kes'

    data = df[features + [target]].dropna()
    X = data[features]
    y = data[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    r2   = r2_score(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))

    return df, model, le, features, r2, rmse, X_test, y_test, predictions


df, model, le, features, r2, rmse, X_test, y_test, preds = load_and_train()

#  HEADER

st.title("Kenya Property Price Predictor")
st.markdown("**Scraped from BuyRentKenya.com · Random Forest Model · 1,733 listings**")
st.markdown("---")

#  TOP METRICS ROW

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(df):,}</div>
        <div class="metric-label">Total Listings</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{r2:.3f}</div>
        <div class="metric-label">Model R² Score</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">KES {rmse/1e6:.1f}M</div>
        <div class="metric-label">Model RMSE</div>
    </div>""", unsafe_allow_html=True)

with col4:
    median_price = df['price_kes'].median()
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">KES {median_price/1e6:.0f}M</div>
        <div class="metric-label">Median Price</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

#  MAIN LAYOUT — Predictor (left) | Charts (right)

left, right = st.columns([1, 2], gap="large")


#Prediction inputs
with left:
    st.subheader("Predict a Property Price")

    listing_type  = st.selectbox("Listing Type",  ["For Sale", "For Rent"])
    property_type = st.selectbox("Property Type", ["House", "Townhouse", "Villa"])
    location      = st.selectbox("Location",      ["Nairobi", "Outside Nairobi"])
    bedrooms      = st.slider("Bedrooms",   1, 10, 3)
    bathrooms     = st.slider("Bathrooms",  1, 10, 3)

    # Encode inputs
    is_sale     = 1 if listing_type  == "For Sale"  else 0
    is_nairobi  = 1 if location      == "Nairobi"   else 0
    total_rooms = bedrooms + bathrooms
    pt_encoded  = {"House": 0, "Townhouse": 1, "Villa": 2}[property_type]

    input_data = pd.DataFrame([[
        bedrooms, bathrooms, is_sale,
        is_nairobi, total_rooms, pt_encoded
    ]], columns=features)

    predicted_price = model.predict(input_data)[0]

    # Display prediction
    price_label = "/month" if listing_type == "For Rent" else ""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="prediction-box">
        <div style="font-size:14px; opacity:0.85">Estimated Price</div>
        <div class="prediction-price">KES {predicted_price:,.0f}</div>
        <div style="font-size:13px; opacity:0.75">{property_type} · {bedrooms} bed · {location}{price_label}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Context: where this falls in the market
    sale_df = df[df['listing_type'] == ('sale' if is_sale else 'rent')]
    pct_rank = (sale_df['price_kes'] < predicted_price).mean() * 100
    st.info(f"📊 This property is priced higher than **{pct_rank:.0f}%** of similar listings in the dataset.")


#Charts
with right:
    st.subheader("Data Insights")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Price Distribution", "By Bedrooms", "Neighbourhoods", "Model Performance"
    ])

    # TAB 1: Price distribution
    with tab1:
        fig, ax = plt.subplots(figsize=(9, 4))
        sale_p = df[df['listing_type'] == 'sale']['price_kes']
        rent_p = df[df['listing_type'] == 'rent']['price_kes']
        ax.hist(np.log10(sale_p), bins=30, alpha=0.7, color='#1565C0', label=f'For Sale (n={len(sale_p):,})')
        ax.hist(np.log10(rent_p), bins=30, alpha=0.7, color='#E64A19', label=f'For Rent (n={len(rent_p):,})')
        ax.set_xlabel('Price (KES)')
        ax.set_ylabel('Count')
        ax.set_title('Price Distribution — Sale vs Rent')
        ax.set_xticks([6, 7, 8, 9])
        ax.set_xticklabels(['1M', '10M', '100M', '1B'])
        ax.legend()
        ax.axvline(np.log10(sale_p.median()), color='#1565C0', linestyle='--', alpha=0.6)
        ax.axvline(np.log10(rent_p.median()), color='#E64A19', linestyle='--', alpha=0.6)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

        col_a, col_b = st.columns(2)
        col_a.metric("Median Sale Price", f"KES {sale_p.median()/1e6:.1f}M")
        col_b.metric("Median Rent/Month", f"KES {rent_p.median()/1e3:.0f}K")

    # TAB 2: Price by bedrooms
    with tab2:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        bed_sale = (df[df['listing_type']=='sale']
                    .groupby('bedrooms')['price_kes'].median()
                    .reset_index())
        bed_sale = bed_sale[bed_sale['bedrooms'] <= 8]
        axes[0].bar(bed_sale['bedrooms'].astype(int),
                    bed_sale['price_kes'] / 1e6,
                    color='#1565C0', edgecolor='white')
        axes[0].set_xlabel('Bedrooms')
        axes[0].set_ylabel('Median Price (KES M)')
        axes[0].set_title('Sale Price by Bedrooms')
        for _, row in bed_sale.iterrows():
            axes[0].text(int(row['bedrooms']), row['price_kes']/1e6 + 1,
                         f"{row['price_kes']/1e6:.0f}M",
                         ha='center', fontsize=8, fontweight='bold')

        bed_rent = (df[df['listing_type']=='rent']
                    .groupby('bedrooms')['price_kes'].median()
                    .reset_index())
        bed_rent = bed_rent[bed_rent['bedrooms'] <= 8]
        axes[1].bar(bed_rent['bedrooms'].astype(int),
                    bed_rent['price_kes'] / 1e3,
                    color='#E64A19', edgecolor='white')
        axes[1].set_xlabel('Bedrooms')
        axes[1].set_ylabel('Median Rent (KES K/mo)')
        axes[1].set_title('Rent by Bedrooms')

        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

    # TAB 3: Neighbourhoods
    with tab3:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        top10 = df['neighbourhood'].value_counts().head(10)
        sns.barplot(x=top10.values, y=top10.index, ax=axes[0],
                    palette='Blues_r', hue=top10.index, legend=False)
        axes[0].set_xlabel('Listings')
        axes[0].set_title('Top 10 Neighbourhoods')

        nairobi_med  = df[df['is_nairobi']==1]['price_kes'].median() / 1e6
        outside_med  = df[df['is_nairobi']==0]['price_kes'].median() / 1e6
        axes[1].bar(['Outside Nairobi', 'Nairobi'],
                    [outside_med, nairobi_med],
                    color=['#2E7D32', '#1565C0'])
        axes[1].set_ylabel('Median Price (KES M)')
        axes[1].set_title('Nairobi Price Premium')
        for i, v in enumerate([outside_med, nairobi_med]):
            axes[1].text(i, v + 1, f'{v:.0f}M', ha='center', fontweight='bold')

        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

        premium = (nairobi_med - outside_med) / outside_med * 100
        st.info(f"🏙️ Nairobi properties are **{premium:.0f}% more expensive** than outside Nairobi on average.")

    # TAB 4: Model performance
    with tab4:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))

        # Actual vs Predicted
        axes[0].scatter(np.log10(y_test), np.log10(preds),
                        alpha=0.4, color='#1565C0', s=15)
        axes[0].plot([6, 9], [6, 9], 'r--', linewidth=1.5, label='Perfect fit')
        axes[0].set_xlabel('Actual Price (KES)')
        axes[0].set_ylabel('Predicted Price (KES)')
        axes[0].set_title(f'Actual vs Predicted\nR² = {r2:.3f}')
        axes[0].set_xticks([6, 7, 8, 9])
        axes[0].set_xticklabels(['1M', '10M', '100M', '1B'])
        axes[0].set_yticks([6, 7, 8, 9])
        axes[0].set_yticklabels(['1M', '10M', '100M', '1B'])
        axes[0].legend()

        # Feature importances
        importances = pd.Series(
            model.feature_importances_,
            index=['Bedrooms','Bathrooms','Is Sale','Is Nairobi',
                   'Total Rooms','Property Type']
        ).sort_values(ascending=True)
        axes[1].barh(importances.index, importances.values, color='#1565C0')
        axes[1].set_xlabel('Importance Score')
        axes[1].set_title('Feature Importances')

        plt.tight_layout()
        st.pyplot(fig)
        plt.close()

        col_a, col_b = st.columns(2)
        col_a.metric("R² Score",  f"{r2:.4f}")
        col_b.metric("RMSE", f"KES {rmse/1e6:.1f}M")


#  FOOTER

st.markdown("---")
st.markdown(
    "**Data source:** Scraped from [BuyRentKenya.com](https://www.buyrentkenya.com)·"
    "**Model:** Random Forest (100 trees) · "
    "**Built with:** Python, Streamlit, scikit-learn, pandas"
)