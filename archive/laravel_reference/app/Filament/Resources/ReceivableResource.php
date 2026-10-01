<?php

namespace App\Filament\Resources;

use App\Models\AccountsReceivable;
use Filament\Forms;
use Filament\Forms\Form;
use Filament\Resources\Resource;
use Filament\Tables;
use Filament\Tables\Table;

class ReceivableResource extends Resource
{
    protected static ?string $model = AccountsReceivable::class;
    protected static ?string $navigationIcon = 'heroicon-o-banknotes';
    protected static ?string $navigationGroup = 'Keuangan';
    protected static ?string $navigationLabel = 'Piutang Pelanggan';
    protected static ?string $pluralModelLabel = 'Piutang';

    public static function form(Form $form): Form
    {
        return $form->schema([
            Forms\Components\Select::make('transaction_id')
                ->relationship('transaction', 'invoice_number')->required(),
            Forms\Components\Select::make('customer_id')
                ->relationship('customer', 'name')->required(),
            Forms\Components\TextInput::make('amount')->numeric()->required(),
            Forms\Components\DatePicker::make('due_date')->required(),
            Forms\Components\Select::make('status')->options(['unpaid' => 'Belum Dibayar', 'paid' => 'Lunas']),
        ]);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('due_date')
            ->columns([
                Tables\Columns\TextColumn::make('transaction.invoice_number')->label('Invoice')->searchable(),
                Tables\Columns\TextColumn::make('customer.name')->label('Pelanggan')->searchable(),
                Tables\Columns\TextColumn::make('amount')->label('Jumlah')->money('IDR')->sortable(),
                Tables\Columns\TextColumn::make('due_date')->label('Jatuh Tempo')->date('d M Y')->sortable(),
                Tables\Columns\TextColumn::make('status')
                    ->badge()
                    ->formatStateUsing(fn (string $state) => $state === 'paid' ? 'Lunas' : 'Belum Dibayar')
                    ->color(fn (string $state) => $state === 'paid' ? 'success' : 'warning'),
                // Indikator visual pembayaran lewat jatuh tempo
                Tables\Columns\TextColumn::make('overdue')
                    ->label('Keterangan')
                    ->state(fn (AccountsReceivable $record) => $record->isOverdue() ? 'Lewat Jatuh Tempo' : '')
                    ->badge()->color('danger'),
            ])
            ->filters([
                Tables\Filters\SelectFilter::make('status')->options(['unpaid' => 'Belum Dibayar', 'paid' => 'Lunas']),
            ])
            ->actions([
                Tables\Actions\Action::make('tandaiLunas')
                    ->label('Tandai Lunas')
                    ->icon('heroicon-m-check')->color('success')
                    ->requiresConfirmation()
                    ->visible(fn (AccountsReceivable $record) => $record->status === 'unpaid')
                    ->action(fn (AccountsReceivable $record) => $record->update(['status' => 'paid'])),
            ]);
    }

    public static function getPages(): array
    {
        return ['index' => Pages\ListReceivables::route('/')];
    }
}
