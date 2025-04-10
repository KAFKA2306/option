import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import Lasso
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# ベーシス分析のための基本クラス
class BitcoinBasisAnalyzer:
    def __init__(self, spot_df, futures_df):
        """
        ビットコイン先物ベーシス分析クラスの初期化

        Parameters:
        -----------
        spot_df : DataFrame
            現物価格データ（インデックスは日時、'close'カラムを含む）
        futures_df : DataFrame
            先物価格データ（インデックスは日時、'close'カラムを含む）
        """
        self.spot_df = spot_df.copy()
        self.futures_df = futures_df.copy()
        self.basis_df = None
        self.calculate_basis()

    def calculate_basis(self):
        """基本的なベーシス指標を計算"""
        # 同じインデックスを持つデータのみを取得
        common_idx = self.spot_df.index.intersection(self.futures_df.index)
        spot = self.spot_df.loc[common_idx]
        futures = self.futures_df.loc[common_idx]

        # ベーシス計算用のデータフレーム作成
        self.basis_df = pd.DataFrame(index=common_idx)
        self.basis_df['spot_price'] = spot['close']
        self.basis_df['futures_price'] = futures['close']

        # 基本ベーシス計算
        self.basis_df['basis'] = self.basis_df['futures_price'] - self.basis_df['spot_price']
        self.basis_df['basis_percent'] = (self.basis_df['basis'] / self.basis_df['spot_price']) * 100

        return self.basis_df

    def calculate_annualized_basis(self, days_to_maturity=30):
        """
        年率換算ベーシスの計算

        Parameters:
        -----------
        days_to_maturity : int
            先物の満期までの日数

        Returns:
        --------
        Series
            年率換算ベーシス
        """
        self.basis_df['annualized_basis'] = ((self.basis_df['futures_price'] /
                                             self.basis_df['spot_price'] - 1) *
                                            (365 / days_to_maturity)) * 100
        return self.basis_df['annualized_basis']

    def calculate_basis_zscore(self, window=30):
        """
        ベーシスのZスコア計算

        Parameters:
        -----------
        window : int
            移動平均と標準偏差の計算ウィンドウ

        Returns:
        --------
        Series
            ベーシスのZスコア
        """
        rolling_mean = self.basis_df['basis_percent'].rolling(window=window).mean()
        rolling_std = self.basis_df['basis_percent'].rolling(window=window).std()
        self.basis_df['basis_zscore'] = (self.basis_df['basis_percent'] - rolling_mean) / rolling_std
        return self.basis_df['basis_zscore']

    def calculate_basis_momentum(self, window=14):
        """
        ベーシスモメンタムの計算

        Parameters:
        -----------
        window : int
            モメンタム計算ウィンドウ

        Returns:
        --------
        Series
            ベーシスモメンタム
        """
        self.basis_df['basis_momentum'] = self.basis_df['basis_percent'].pct_change().rolling(window=window).sum()
        return self.basis_df['basis_momentum']

    def calculate_volatility_adjusted_basis(self, vol_window=30):
        """
        ボラティリティ調整済みベーシスの計算

        Parameters:
        -----------
        vol_window : int
            ボラティリティ計算ウィンドウ

        Returns:
        --------
        Series
            ボラティリティ調整済みベーシス
        """
        spot_returns = self.basis_df['spot_price'].pct_change()
        self.basis_df['spot_volatility'] = spot_returns.rolling(window=vol_window).std() * np.sqrt(252) # Assuming daily data for annualization
        self.basis_df['vol_adjusted_basis'] = self.basis_df['basis_percent'] / self.basis_df['spot_volatility']
        return self.basis_df['vol_adjusted_basis']

    def detect_market_regime(self, n_states=3):
        """
        簡易的な市場レジーム検出（HMMの代わりに閾値ベース）

        Parameters:
        -----------
        n_states : int
            検出する状態数

        Returns:
        --------
        Series
            市場レジーム（0:バックワーデーション, 1:中立, 2:コンタンゴ）
        """
        self.basis_df['market_regime'] = 1  # デフォルトは中立
        # Handle cases with insufficient data or NaNs for percentiles
        valid_basis_percent = self.basis_df['basis_percent'].dropna()
        if len(valid_basis_percent) < 3: # Need at least 3 points for percentiles
             print("Warning: Insufficient data for market regime detection.")
             return self.basis_df['market_regime']

        percentiles = np.percentile(valid_basis_percent, [33, 67])

        self.basis_df.loc[self.basis_df['basis_percent'] < percentiles[0], 'market_regime'] = 0
        self.basis_df.loc[self.basis_df['basis_percent'] > percentiles[1], 'market_regime'] = 2

        # レジーム遷移カウント
        transitions = self.basis_df['market_regime'].diff().fillna(0) != 0
        transition_count = transitions.sum()
        print(f"レジーム遷移回数: {transition_count}")

        return self.basis_df['market_regime']

    def calculate_dynamic_position_sizing(self, risk_capital=10000, max_risk_per_trade=0.02):
        """
        動的ポジションサイジングの計算

        Parameters:
        -----------
        risk_capital : float
            リスク資本額
        max_risk_per_trade : float
            トレードごとの最大リスク割合

        Returns:
        --------
        Series
            計算されたポジションサイズ
        """
        # ATR計算（近似版） - Requires high/low data, using close price diff as proxy
        # A more accurate ATR requires high/low prices in the input DataFrames
        # self.spot_df and self.futures_df need 'high' and 'low' columns for proper ATR
        # Using close price diff as a simplified volatility measure for now
        tr = abs(self.basis_df['futures_price'] - self.basis_df['futures_price'].shift(1))
        atr = tr.rolling(14).mean()

        # ポジションサイズの計算
        risk_amount = risk_capital * max_risk_per_trade
        # Avoid division by zero or NaN in ATR
        atr_safe = atr.replace(0, np.nan).fillna(method='ffill').fillna(1) # Fill NaNs and zeros with 1 as fallback
        self.basis_df['position_size'] = (risk_amount / atr_safe).clip(upper=risk_capital) # Limit position size

        return self.basis_df['position_size']

    def generate_trading_signals(self, zscore_threshold=2.0):
        """
        取引シグナルの生成

        Parameters:
        -----------
        zscore_threshold : float
            シグナル生成のZスコア閾値

        Returns:
        --------
        Series
            取引シグナル（-1:売り, 0:ホールド, 1:買い）
        """
        if 'basis_zscore' not in self.basis_df.columns:
            self.calculate_basis_zscore()

        self.basis_df['signal'] = 0  # デフォルトはホールド

        # コンタンゴが過剰（先物価格が高すぎる）→ 先物売り/現物買い
        self.basis_df.loc[self.basis_df['basis_zscore'] > zscore_threshold, 'signal'] = -1

        # バックワーデーションが過剰（先物価格が安すぎる）→ 先物買い/現物売り
        self.basis_df.loc[self.basis_df['basis_zscore'] < -zscore_threshold, 'signal'] = 1

        # Avoid trading on NaN signals
        self.basis_df['signal'] = self.basis_df['signal'].fillna(0)

        return self.basis_df['signal']

    def backtest_basis_strategy(self, initial_capital=10000, transaction_cost=0.001):
        """
        ベーシス戦略のバックテスト

        Parameters:
        -----------
        initial_capital : float
            初期資本金
        transaction_cost : float
            取引コスト（割合）

        Returns:
        --------
        DataFrame
            バックテスト結果（シグナル、リターン、累積リターン、資産価値など）
        """
        if 'signal' not in self.basis_df.columns:
            self.generate_trading_signals()

        # 戦略リターンの計算（シグナルの1日後のリターンを取得）
        # Assuming we trade based on previous day's signal
        basis_returns = self.basis_df['basis_percent'].pct_change() # Using basis percent change as proxy return
        self.basis_df['strategy_return'] = self.basis_df['signal'].shift(1) * basis_returns

        # 取引コストを考慮
        trades = self.basis_df['signal'].diff().fillna(0) != 0
        self.basis_df['transaction_costs'] = trades * transaction_cost
        self.basis_df['net_return'] = self.basis_df['strategy_return'] - self.basis_df['transaction_costs']

        # 累積リターンと資産価値
        self.basis_df['cumulative_return'] = (1 + self.basis_df['net_return'].fillna(0)).cumprod() - 1
        self.basis_df['equity'] = initial_capital * (1 + self.basis_df['cumulative_return'])

        # パフォーマンス指標
        total_return = self.basis_df['equity'].iloc[-1] / initial_capital - 1
        num_trades = trades.sum()
        winning_trades = self.basis_df[trades]['net_return'] > 0
        win_rate = winning_trades.sum() / num_trades if num_trades > 0 else 0

        print(f"トータルリターン: {total_return:.2%}")
        print(f"トレード回数: {num_trades}")
        print(f"勝率: {win_rate:.2%}")

        return self.basis_df[['signal', 'strategy_return', 'net_return', 'cumulative_return', 'equity']]

    def plot_basis_analysis(self, figsize=(15, 12)):
        """ベーシス分析の結果をプロット"""
        if self.basis_df is None:
            raise ValueError("先にベーシス計算を実行してください")

        fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)

        # 価格チャート
        axes[0].plot(self.basis_df.index, self.basis_df['spot_price'], label='現物価格')
        axes[0].plot(self.basis_df.index, self.basis_df['futures_price'], label='先物価格')
        axes[0].set_title('ビットコイン現物・先物価格')
        axes[0].legend()
        axes[0].grid(True)

        # ベーシスチャート
        ax1b = axes[1].twinx() # Second y-axis for basis_percent
        axes[1].plot(self.basis_df.index, self.basis_df['basis'], label='ベーシス ($)', color='tab:blue')
        ax1b.plot(self.basis_df.index, self.basis_df['basis_percent'], label='ベーシス (%)', color='tab:orange', linestyle='--')
        axes[1].set_ylabel('Basis ($)', color='tab:blue')
        ax1b.set_ylabel('Basis (%)', color='tab:orange')
        axes[1].set_title('ベーシスとベーシス率')
        axes[1].legend(loc='upper left')
        ax1b.legend(loc='upper right')
        axes[1].grid(True)

        # Zスコアチャート
        if 'basis_zscore' in self.basis_df.columns:
            axes[2].plot(self.basis_df.index, self.basis_df['basis_zscore'], label='ベーシスZスコア')
            axes[2].axhline(y=2, color='r', linestyle='--', label='上限閾値 (Z=2)')
            axes[2].axhline(y=-2, color='g', linestyle='--', label='下限閾値 (Z=-2)')
            axes[2].set_title('ベーシスZスコア')
            axes[2].legend()
            axes[2].grid(True)
        else:
             axes[2].set_title('ベーシスZスコア (未計算)')
             axes[2].grid(True)


        # 市場レジームチャート
        if 'market_regime' in self.basis_df.columns:
            # カラーマッピング
            cmap = {0: 'red', 1: 'gray', 2: 'green'}
            regime_colors = [cmap.get(regime, 'gray') for regime in self.basis_df['market_regime']]

            # Use scatter plot for regimes
            axes[3].scatter(self.basis_df.index, self.basis_df['market_regime'],
                         c=regime_colors, label='市場レジーム', s=10) # Smaller points
            axes[3].set_yticks([0, 1, 2])
            axes[3].set_yticklabels(['バックワーデーション', '中立', 'コンタンゴ'])
            axes[3].set_title('市場レジーム分類')
            axes[3].grid(True)
        else:
            axes[3].set_title('市場レジーム (未計算)')
            axes[3].grid(True)


        plt.tight_layout()
        plt.show()

        # 戦略パフォーマンスのプロット（バックテストが実行されている場合）
        if 'equity' in self.basis_df.columns:
            plt.figure(figsize=(12, 6))
            plt.plot(self.basis_df.index, self.basis_df['equity'])
            plt.title('ベーシス戦略のパフォーマンス')
            plt.xlabel('Date')
            plt.ylabel('Equity')
            plt.grid(True)
            plt.show()

# サンプルデータ生成（実際のアプリケーションでは実データに置き換え）
def generate_sample_data(n_periods=100, start_date='2025-01-01'):
    """サンプルデータの生成"""
    np.random.seed(42)

    dates = pd.date_range(start=start_date, periods=n_periods, freq='D')

    # 価格シミュレーション
    spot_price_start = 80000
    spot_prices = [spot_price_start]

    for _ in range(n_periods-1):
        change = np.random.normal(0, 0.02)  # 2%のボラティリティ
        new_price = spot_prices[-1] * (1 + change)
        spot_prices.append(new_price)

    # 先物プレミアムのシミュレーション（市場レジームを含む）
    premiums = []
    regime_state = 1  # 初期状態は中立

    for i in range(n_periods):
        # 状態遷移
        if np.random.random() < 0.05:  # 5%の確率でレジーム変化
            regime_state = np.random.choice([0, 1, 2])

        # レジームに応じたプレミアム
        if regime_state == 0:  # バックワーデーション
            premium = np.random.uniform(-0.03, -0.01)
        elif regime_state == 1:  # 中立
            premium = np.random.uniform(-0.01, 0.01)
        else:  # コンタンゴ
            premium = np.random.uniform(0.01, 0.03)

        premiums.append(premium)

    # データフレーム作成
    spot_df = pd.DataFrame(index=dates, data={'close': spot_prices})
    futures_df = pd.DataFrame(index=dates, data={'close': [p * (1 + premium) for p, premium in zip(spot_prices, premiums)]})

    return spot_df, futures_df

# メイン処理
if __name__ == "__main__":
    # サンプルデータ生成
    spot_df, futures_df = generate_sample_data(n_periods=180)

    # ベーシス分析
    analyzer = BitcoinBasisAnalyzer(spot_df, futures_df)

    # 各種指標の計算
    analyzer.calculate_annualized_basis(days_to_maturity=30)
    analyzer.calculate_basis_zscore(window=30)
    analyzer.calculate_basis_momentum(window=14)
    analyzer.calculate_volatility_adjusted_basis(vol_window=30)
    analyzer.detect_market_regime()
    analyzer.generate_trading_signals(zscore_threshold=1.5)

    # バックテスト
    analyzer.backtest_basis_strategy(initial_capital=10000, transaction_cost=0.001)

    # 結果の可視化
    analyzer.plot_basis_analysis()

    # 最初の10日間のデータを表示
    print("\n最初の10日間のデータ:")
    print(analyzer.basis_df.head(10)) 