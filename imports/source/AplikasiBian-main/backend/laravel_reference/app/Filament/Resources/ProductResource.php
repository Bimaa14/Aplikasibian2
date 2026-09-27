<?php

namespace App\Filament\Resources;

use App\Models\Product;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class ProductResource extends Resource
{
    protected static ?string $model = Product::class;
    protected static ?string $navigationIcon = 'heroicon-o-cube';
    protected static ?string $navigationGroup = 'Data Master';
    protected static ?string $pluralModelLabel = 'Produk';

    public static function form(Form $form): Form
    {
        return $form->schema([
            Forms\Components\Select::make('type')
                ->options(['barang' => 'Barang', 'jasa' => 'Jasa Servis'])->required()->live(),
            Forms\Components\TextInput::make('sku')->required()->unique(ignoreRecord: true),
            Forms\Components\TextInput::make('name')->required(),
            Forms\Components\TextInput::make('brand'),
            Forms\Components\TextInput::make('size'),
            Forms\Components\TextInput::make('stock')->numeric()
                ->hidden(fn (Forms\Get $get) => $get('type') === 'jasa'),
            Forms\Components\TextInput::make('cost_price')->numeric()->label('Modal (Harga Pokok)')
                ->hidden(fn (Forms\Get $get) => $get('type') === 'jasa'),
            Forms\Components\TextInput::make('selling_price')->numeric()->label('Harga Jual')->required(),
            Forms\Components\TextInput::make('service_fee')->numeric()->label('Komisi Montir')
                ->hidden(fn (Forms\Get $get) => $get('type') !== 'jasa'),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('sku')->searchable()->copyable(),
                Tables\Columns\TextColumn::make('name')->searchable(),
                Tables\Columns\TextColumn::make('type')->badge()
                    ->formatStateUsing(fn (string $state) => $state === 'jasa' ? 'Jasa' : 'Barang')
                    ->color(fn (string $state) => $state === 'jasa' ? 'info' : 'warning'),
                Tables\Columns\TextColumn::make('brand'),
                Tables\Columns\TextColumn::make('size'),
                Tables\Columns\TextColumn::make('stock')
                    ->color(fn ($state) => $state <= 4 ? 'danger' : null),
                Tables\Columns\TextColumn::make('cost_price')->money('IDR')->label('Modal'),
                Tables\Columns\TextColumn::make('selling_price')->money('IDR')->label('Harga Jual'),
                Tables\Columns\TextColumn::make('service_fee')->money('IDR')->label('Komisi'),
            ])
            ->filters([
                Tables\Filters\SelectFilter::make('type')->options(['barang' => 'Barang', 'jasa' => 'Jasa']),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => Pages\ListProducts::route('/'),
            'create' => Pages\CreateProduct::route('/create'),
            'edit' => Pages\EditProduct::route('/{record}/edit'),
        ];
    }
}
